import argparse
import subprocess
import sys
import time
from pathlib import Path


REPO_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = Path(r"C:\Program Files (x86)\Steam\steamapps\common\Grand Theft Auto IV\GTAIV\scripts")
RELOAD_TRIGGER = REPO_DIR / ".reload_request"


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

    print(f"Watching {args.remote}/{args.branch} from {REPO_DIR}")

    last_remote_sha = None
    while True:
        try:
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
                    request_ingame_reload()
                last_remote_sha = current_remote_sha
        except KeyboardInterrupt:
            print("Stopped.")
            return 0
        except Exception as exc:
            print(f"[watch_remote] {exc}")

        time.sleep(args.interval)


if __name__ == "__main__":
    raise SystemExit(main())
