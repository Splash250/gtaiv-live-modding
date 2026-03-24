import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path


REPO_DIR = Path(__file__).resolve().parent
GTAIV_DIR = Path(r"C:\Program Files (x86)\Steam\steamapps\common\Grand Theft Auto IV\GTAIV")
SCRIPTS_DIR = Path(r"C:\Program Files (x86)\Steam\steamapps\common\Grand Theft Auto IV\GTAIV\scripts")
RELOAD_TRIGGER = REPO_DIR / ".reload_request"
STATE_FILE = REPO_DIR / ".live_state.json"
LOGS_DIR = REPO_DIR / "logs"
RUNTIME_DIR = REPO_DIR / ".watch_remote_runtime"
LOG_SOURCE_FILES = [
    GTAIV_DIR / "ScriptHookDotNet.log",
    GTAIV_DIR / "scripthook.log",
    GTAIV_DIR / "asilog.txt",
    GTAIV_DIR / "AdvancedHookInit.log",
    GTAIV_DIR / "GTAIV_d3d9.log",
]
ERROR_MARKERS = [
    " error",
    " errors in script",
    "exception",
    "fatal",
    "accessviolation",
    "failed",
]
ERROR_TAIL_LINE_COUNT = 80
LIVE_FILE_SUFFIXES = {".cs", ".ini"}
DEFAULT_STATE = {
    "last_pulled_sha": "",
    "last_deployed_sha": "",
    "last_reload_requested_sha": "",
    "last_skip_reason": "",
    "log_tail_hashes": {},
}


def log(message):
    print(message, flush=True)


def run_git(args):
    result = subprocess.run(
        ["git"] + args,
        cwd=REPO_DIR,
        text=True,
        capture_output=True,
    )
    return result


def git_output(args):
    result = run_git(args)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "git command failed")
    return result.stdout.strip()


def has_uncommitted_changes():
    result = run_git(["status", "--porcelain"])
    return bool(result.stdout.strip())


def status_lines():
    result = run_git(["status", "--porcelain"])
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git status failed")
    return [line for line in result.stdout.splitlines() if line.strip()]


def ensure_remote_exists(remote_name):
    remotes = git_output(["remote"]).splitlines()
    if remote_name not in remotes:
        raise RuntimeError(
            f"Remote '{remote_name}' is not configured. Add it first with "
            f"'git remote add {remote_name} <url>'."
        )


def ensure_branch_exists(remote_name, branch_name):
    result = run_git(["ls-remote", "--heads", remote_name, branch_name])
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "failed to query remote")
    if not result.stdout.strip():
        raise RuntimeError(f"Remote branch '{remote_name}/{branch_name}' does not exist yet.")


def local_head():
    return git_output(["rev-parse", "HEAD"])


def remote_head(remote_name, branch_name):
    result = run_git(["ls-remote", remote_name, f"refs/heads/{branch_name}"])
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "failed to query remote head")

    line = result.stdout.strip()
    if not line:
        raise RuntimeError(f"Remote branch '{remote_name}/{branch_name}' does not exist yet.")

    return line.split()[0]


def changed_files_between(base_sha, target_sha):
    if not base_sha or not target_sha or base_sha == target_sha:
        return []

    output = git_output(["diff", "--name-only", base_sha, target_sha])
    return [line.strip() for line in output.splitlines() if line.strip()]


def is_live_repo_file(path_text):
    return Path(path_text).suffix.lower() in LIVE_FILE_SUFFIXES


def changed_live_files(paths):
    return [path for path in paths if is_live_repo_file(path)]


def pull_latest(remote_name, branch_name):
    result = run_git(["pull", "--ff-only", remote_name, branch_name])
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "git pull failed")

    output = result.stdout.strip()
    if output:
        print(output)


def ensure_scripts_dir():
    if not SCRIPTS_DIR.exists():
        raise RuntimeError(f"GTA IV scripts folder does not exist: {SCRIPTS_DIR}")


def ensure_runtime_dir():
    RUNTIME_DIR.mkdir(exist_ok=True)


def repo_files_to_link():
    for path in REPO_DIR.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".cs", ".ini"}:
            continue
        yield path


def create_missing_hardlinks():
    ensure_scripts_dir()

    created = []
    skipped = []
    for source in repo_files_to_link():
        target = SCRIPTS_DIR / source.name
        if target.exists():
            skipped.append(target.name)
            continue

        target.hardlink_to(source)
        created.append(target.name)

    if created:
        log("Created hard links:")
        for name in created:
            log(f"  {name}")

    if skipped:
        log("Skipped existing targets:")
        for name in skipped:
            log(f"  {name}")


def request_ingame_reload():
    RELOAD_TRIGGER.write_text("reload\n", encoding="utf-8")
    log(f"Requested in-game reload via {RELOAD_TRIGGER}")


def latest_commit_subject():
    return git_output(["log", "-1", "--pretty=%s"])


def ensure_logs_dir():
    LOGS_DIR.mkdir(exist_ok=True)


def load_state():
    if not STATE_FILE.exists():
        return dict(DEFAULT_STATE)

    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return dict(DEFAULT_STATE)

    state = dict(DEFAULT_STATE)
    for key in DEFAULT_STATE:
        value = data.get(key, DEFAULT_STATE[key])
        if isinstance(DEFAULT_STATE[key], dict):
            state[key] = value if isinstance(value, dict) else {}
        else:
            state[key] = value if isinstance(value, str) else ""
    return state


def save_state(state):
    serializable = {key: state.get(key, "") for key in DEFAULT_STATE}
    STATE_FILE.write_text(json.dumps(serializable, indent=2) + "\n", encoding="utf-8")


def mark_skip(state, pulled_sha, reason):
    state["last_pulled_sha"] = pulled_sha or state.get("last_pulled_sha", "")
    state["last_skip_reason"] = reason
    save_state(state)


def read_log_tail(source, line_count=ERROR_TAIL_LINE_COUNT):
    try:
        lines = source.read_text(encoding="utf-8", errors="ignore").splitlines()
    except (OSError, PermissionError):
        return ""

    if not lines:
        return ""

    return "\n".join(lines[-line_count:]).lower()


def log_tail_hash(tail_text):
    return hashlib.sha256(tail_text.encode("utf-8")).hexdigest()


def sync_runtime_logs(state):
    ensure_logs_dir()

    changed = []
    hashes = state.setdefault("log_tail_hashes", {})
    state_changed = False
    for source in LOG_SOURCE_FILES:
        if not source.exists():
            continue

        tail_text = read_log_tail(source)
        if not tail_text or not any(marker in tail_text for marker in ERROR_MARKERS):
            if source.name in hashes:
                hashes.pop(source.name, None)
                state_changed = True
            continue

        current_tail_hash = log_tail_hash(tail_text)
        if hashes.get(source.name) == current_tail_hash:
            continue

        target = LOGS_DIR / source.name
        source_bytes = source.read_bytes()
        target_bytes = target.read_bytes() if target.exists() else None
        hashes[source.name] = current_tail_hash
        state_changed = True
        if target_bytes == source_bytes:
            continue

        shutil.copy2(source, target)
        changed.append(target.name)

    if state_changed:
        save_state(state)

    if changed:
        log("Updated repo log snapshots:")
        for name in changed:
            log(f"  {name}")

    return changed


def commit_and_push_logs(remote_name, branch_name, state):
    changed_logs = sync_runtime_logs(state)
    if not changed_logs:
        return False

    run_git(["add", "logs"])

    commit_message = datetime.now().strftime("log_%Y%m%d_%H%M%S")
    commit_result = run_git(["commit", "-m", commit_message])
    if commit_result.returncode != 0:
        output = (commit_result.stderr.strip() or commit_result.stdout.strip() or "git commit failed")
        if "nothing to commit" in output.lower():
            return False
        raise RuntimeError(output)

    log(commit_result.stdout.strip())

    push_result = run_git(["push", remote_name, f"HEAD:{branch_name}"])
    if push_result.returncode != 0:
        raise RuntimeError(push_result.stderr.strip() or push_result.stdout.strip() or "git push failed")

    if push_result.stdout.strip():
        log(push_result.stdout.strip())
    if push_result.stderr.strip():
        log(push_result.stderr.strip())

    return True


def print_reload_decision(decision, reason):
    log(f"[deploy] {decision}: {reason}")


def print_repo_status(lines):
    if lines:
        log(f"[repo] DIRTY ({len(lines)} change(s))")
        for line in lines:
            log(f"  {line}")
    else:
        log("[repo] CLEAN")


def main():
    parser = argparse.ArgumentParser(
        description="Poll a git remote and fast-forward pull when the remote branch changes."
    )
    parser.add_argument("--remote", default="origin", help="Remote name to watch. Default: origin")
    parser.add_argument("--branch", default="main", help="Remote branch to watch. Default: main")
    parser.add_argument(
        "--interval",
        type=int,
        default=10,
        help="Polling interval in seconds. Default: 10",
    )
    parser.add_argument(
        "--unsafe-auto-reload",
        action="store_true",
        help="Reload after any non-log pull, even when no live .cs/.ini files changed.",
    )
    parser.add_argument(
        "--runtime-log",
        default=str(RUNTIME_DIR / "watch_remote.log"),
        help="Optional runtime log path. Use '' to disable file logging. Default: .watch_remote_runtime/watch_remote.log",
    )
    args = parser.parse_args()

    if args.interval < 2:
        print("Interval too low; use 2 seconds or more.", file=sys.stderr, flush=True)
        return 1

    ensure_remote_exists(args.remote)
    ensure_branch_exists(args.remote, args.branch)
    ensure_runtime_dir()
    state = load_state()
    create_missing_hardlinks()
    current_local_sha = local_head()
    current_remote_sha = remote_head(args.remote, args.branch)
    repo_lines = status_lines()

    runtime_log_path = args.runtime_log.strip()
    if runtime_log_path:
        log_path = Path(runtime_log_path)
        if not log_path.is_absolute():
            log_path = REPO_DIR / log_path
        log(f"[runtime] log path reserved: {log_path}")
    else:
        log("[runtime] file logging disabled")

    log(f"Watching {args.remote}/{args.branch} from {REPO_DIR}")
    if args.unsafe_auto_reload:
        log("[mode] unsafe-auto-reload enabled")
    else:
        log("[mode] safe live deploy")
    log(f"Initial local HEAD:  {current_local_sha}")
    log(f"Initial remote HEAD: {current_remote_sha}")
    print_repo_status(repo_lines)

    last_remote_sha = current_remote_sha
    while True:
        try:
            logs_pushed = commit_and_push_logs(args.remote, args.branch, state)
            if logs_pushed:
                last_remote_sha = remote_head(args.remote, args.branch)

            current_remote_sha = remote_head(args.remote, args.branch)
            current_local_sha = local_head()

            if current_remote_sha != last_remote_sha:
                log(f"Detected remote update: {last_remote_sha} -> {current_remote_sha}")
                if has_uncommitted_changes():
                    print_reload_decision("skip", "repo has uncommitted local changes")
                    print_repo_status(status_lines())
                    mark_skip(state, "", "repo_has_uncommitted_changes")
                else:
                    pulled_paths = changed_files_between(last_remote_sha, current_remote_sha)
                    pull_latest(args.remote, args.branch)
                    state["last_pulled_sha"] = current_remote_sha
                    create_missing_hardlinks()
                    live_paths = changed_live_files(pulled_paths)
                    if latest_commit_subject().startswith("log_"):
                        print_reload_decision("skip", "pulled log-only commit")
                        mark_skip(state, current_remote_sha, "log_only_commit")
                    elif args.unsafe_auto_reload:
                        request_ingame_reload()
                        state["last_deployed_sha"] = current_remote_sha
                        state["last_reload_requested_sha"] = current_remote_sha
                        state["last_skip_reason"] = ""
                        save_state(state)
                        print_reload_decision("reload", "unsafe mode bypassed live-file gating")
                    elif live_paths:
                        if state.get("last_reload_requested_sha") == current_remote_sha:
                            print_reload_decision("skip", "reload for this commit was already requested earlier")
                            mark_skip(state, current_remote_sha, "duplicate_reload_request")
                        else:
                            log("Pulled live files:")
                            for path in live_paths:
                                log(f"  {path}")
                            request_ingame_reload()
                            state["last_deployed_sha"] = current_remote_sha
                            state["last_reload_requested_sha"] = current_remote_sha
                            state["last_skip_reason"] = ""
                            save_state(state)
                            print_reload_decision("reload", "live .cs/.ini files changed")
                    else:
                        print_reload_decision("skip", "pulled update changed no live .cs/.ini files")
                        mark_skip(state, current_remote_sha, "no_live_file_changes")
                last_remote_sha = current_remote_sha
        except KeyboardInterrupt:
            log("Stopped.")
            return 0
        except Exception as exc:
            log(f"[watch_remote] {exc}")

        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
