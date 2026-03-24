import argparse
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
LOGS_DIR = REPO_DIR / "logs"
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
        print("Created hard links:")
        for name in created:
            print(f"  {name}")

    if skipped:
        print("Skipped existing targets:")
        for name in skipped:
            print(f"  {name}")


def request_ingame_reload():
    RELOAD_TRIGGER.write_text("reload\n", encoding="utf-8")
    print(f"Requested in-game reload via {RELOAD_TRIGGER}")


def latest_commit_subject():
    return git_output(["log", "-1", "--pretty=%s"])


def ensure_logs_dir():
    LOGS_DIR.mkdir(exist_ok=True)


def read_log_tail(source, line_count=ERROR_TAIL_LINE_COUNT):
    try:
        lines = source.read_text(encoding="utf-8", errors="ignore").splitlines()
    except (OSError, PermissionError):
        return ""

    if not lines:
        return ""

    return "\n".join(lines[-line_count:]).lower()


def log_contains_error(source):
    tail_text = read_log_tail(source)
    if not tail_text:
        return False

    return any(marker in tail_text for marker in ERROR_MARKERS)


def sync_runtime_logs():
    ensure_logs_dir()

    changed = []
    for source in LOG_SOURCE_FILES:
        if not source.exists():
            continue
        if not log_contains_error(source):
            continue

        target = LOGS_DIR / source.name
        source_bytes = source.read_bytes()
        target_bytes = target.read_bytes() if target.exists() else None
        if target_bytes == source_bytes:
            continue

        shutil.copy2(source, target)
        changed.append(target.name)

    if changed:
        print("Updated repo log snapshots:")
        for name in changed:
            print(f"  {name}")

    return changed


def commit_and_push_logs(remote_name, branch_name):
    changed_logs = sync_runtime_logs()
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

    print(commit_result.stdout.strip())

    push_result = run_git(["push", remote_name, f"HEAD:{branch_name}"])
    if push_result.returncode != 0:
        raise RuntimeError(push_result.stderr.strip() or push_result.stdout.strip() or "git push failed")

    if push_result.stdout.strip():
        print(push_result.stdout.strip())
    if push_result.stderr.strip():
        print(push_result.stderr.strip())

    return True


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
    args = parser.parse_args()

    if args.interval < 2:
        print("Interval too low; use 2 seconds or more.", file=sys.stderr)
        return 1

    ensure_remote_exists(args.remote)
    ensure_branch_exists(args.remote, args.branch)
    create_missing_hardlinks()
    commit_and_push_logs(args.remote, args.branch)

    print(f"Watching {args.remote}/{args.branch} from {REPO_DIR}")

    last_remote_sha = None
    while True:
        try:
            logs_pushed = commit_and_push_logs(args.remote, args.branch)
            if logs_pushed:
                last_remote_sha = remote_head(args.remote, args.branch)

            current_remote_sha = remote_head(args.remote, args.branch)
            current_local_sha = local_head()

            if last_remote_sha is None:
                last_remote_sha = current_remote_sha
                print(f"Initial local HEAD:  {current_local_sha}")
                print(f"Initial remote HEAD: {current_remote_sha}")

            if current_remote_sha != last_remote_sha:
                print(f"Detected remote update: {last_remote_sha} -> {current_remote_sha}")
                if has_uncommitted_changes():
                    print("Skipping pull because the repo has uncommitted local changes.")
                else:
                    pull_latest(args.remote, args.branch)
                    create_missing_hardlinks()
                    if not latest_commit_subject().startswith("log_"):
                        request_ingame_reload()
                    else:
                        print("Pulled log-only update; skipping in-game reload.")
                last_remote_sha = current_remote_sha
        except KeyboardInterrupt:
            print("Stopped.")
            return 0
        except Exception as exc:
            print(f"[watch_remote] {exc}")

        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
