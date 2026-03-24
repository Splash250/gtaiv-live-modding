# gtaiv-live-modding

Small GTA IV ScriptHook .NET scripts for live modding experiments.

## Remote Watcher

Run `python watch_remote.py` inside this repo to poll `origin/main` and fast-forward pull when the remote changes.
Run `python watch_remote.py --unsafe-auto-reload` if you want to bypass safe live-file gating and reload after any non-log pull.
Run `python watch_remote.py --runtime-log ""` if you want to disable the default ignored runtime log path entirely.

The watcher will skip pulls when the repo has uncommitted local changes.
It also scans the repo for `.cs` and `.ini` files, validates the matching targets in the GTA IV `scripts` folder, creates missing hard links, and repairs stale copied targets when safe both on startup and after every successful pull.
After a successful pull, it only writes a reload trigger file when the pulled changes include live `.cs` or `.ini` files.
It also snapshots GTA IV runtime logs into the repo `logs` folder, but only when the live logs appear to contain errors and the error tail changed since the last snapshot. Those error snapshots are committed as `log_DATETIME` and pushed automatically.
Remote code pulls take priority over log snapshot pushes, so log-side activity is deferred until the local repo is back at remote HEAD.
Log-only sync intentionally skips in-game script reload to avoid an infinite push/pull/reload loop.
The default mode is safe live deploy and prints explicit startup state plus deploy decisions for each remote change.
Watcher runtime files should live only in ignored paths such as `.watch_remote_runtime`.

## In-Game Auto Reload

`AutoReloadBridge.cs` runs inside GTA IV and watches for the reload trigger file.
When the watcher drops that trigger after a successful pull, the bridge calls ScriptHook .NET's `ReloadScripts` console command in-game.
