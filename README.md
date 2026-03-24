# gtaiv-live-modding

Small GTA IV ScriptHook .NET scripts for live modding experiments.

## Remote Watcher

Run `python watch_remote.py` inside this repo to poll `origin/main` and fast-forward pull when the remote changes.

The watcher will skip pulls when the repo has uncommitted local changes.
It also scans the repo for `.cs` and `.ini` files and creates missing hard links into the GTA IV `scripts` folder both on startup and after every successful pull.
After a successful pull, it writes a reload trigger file.

## In-Game Auto Reload

`AutoReloadBridge.cs` runs inside GTA IV and watches for the reload trigger file.
When the watcher drops that trigger after a successful pull, the bridge calls ScriptHook .NET's `ReloadScripts` console command in-game.
