# Update or remove the kit

PY = `py -3` on Windows, `python3` on Mac/Linux.

## Update

Your own files are never in the download: `config.json`, `data/`, `journal/`, `my-strategy/STRATEGY.md`, your
`rules/*.py`. Keep them.

1. **Get the new version.** With Git: `git pull` in the kit folder. With a ZIP: download the new one and copy the new
   files over the old folder, without deleting your own files above.
2. **If `mt5/TraderClaw.mq5` changed** (`git pull` lists it, or `PY -m traderclaw status` shows an older service
   version than the file's `#property version`): copy it to `MQL5/Services/` again, compile it (F7), then in Navigator >
   Services right-click TraderClaw > **Stop**, then **Start**.
3. **Restart the engine** (it re-reads config and rules by itself, but not its own code):
   - Mac: `launchctl kickstart -k gui/$(id -u)/com.traderclaw.engine`
   - Windows: Task Scheduler > TraderClaw engine > End, then Run (or sign out and in). Startup-folder install: end
     `pythonw.exe` in Task Manager, then run `scripts/windows/install-startup.ps1` again.
   - Linux: `systemctl --user restart traderclaw`
4. `PY -m traderclaw status` and `PY -m unittest discover -s tests`.

## Uninstall

1. **The startup job:**
   - Mac: `launchctl bootout gui/$(id -u)/com.traderclaw.engine; rm ~/Library/LaunchAgents/com.traderclaw.engine.plist`
   - Windows (PowerShell): `Unregister-ScheduledTask -TaskName "TraderClaw engine" -Confirm:$false`, and delete
     "TraderClaw engine" from the Startup folder (Win+R, `shell:startup`) if it's there.
   - Linux: `systemctl --user disable --now traderclaw`
2. **The MT5 service:** Navigator > Services > right-click TraderClaw > **Remove**. Stopping it removes its lines from
   your charts. Leftovers (from a crash): Ctrl+B in MT5 lists objects; delete those starting with `TCK_`. Then delete
   `TraderClaw.mq5` and `TraderClaw.ex5` from `MQL5/Services/`.
3. **The export folder:** delete `MQL5/Files/traderclaw/`. It holds copies of your positions and trade history.
4. **Telegram (if you set it up):** delete `~/.config/traderclaw/`, and in @BotFather use /deletebot (or /revoke).
5. **The kit folder** last, after saving anything you want from `journal/` and `my-strategy/`.
