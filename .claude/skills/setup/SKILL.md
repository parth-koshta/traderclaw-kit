---
name: setup
description: Set up the TraderClaw kit end to end for this user - MT5 export service, config, chart levels, phone alerts, startup job, journal and AI review. Use on "set me up", "install this", "get started", "setup", or when config.json doesn't exist yet.
---

# Setup

Read `AGENTS.md` first (hard rules). Go step by step: say what each step does in one line, verify it before the next,
and if something fails, look it up in `docs/troubleshooting.md`. The user clicks in MT5; you never operate their MT5
window. Ask before writing inside the MT5 folders, before installing the startup job, and before any paid AI review.
`docs/setup.md` is the same procedure for humans: point the user to it if they'd rather do a step themselves.

`PY` below = `py -3` on Windows, `python3` on macOS/Linux. Windows + Claude Code: your shell is Git Bash, so run Windows
programs through `powershell -NoProfile -Command "..."` and write paths with `/`.

## 1. Check what they have
- **MetaTrader 5 desktop**, installed and logged in (a demo is fine). On a Mac, the official MetaTrader 5 app.
- **Python 3.9+**: `PY --version`. If missing, they install it from python.org (Windows: tick "Add python.exe to PATH").
- **Where this folder is.** On a Mac it must not be in Documents, Desktop, Downloads or iCloud Drive (macOS blocks the
  background engine there): offer to move it to `~/traderclaw-kit` and continue from there.
- **Their symbols**, exactly as in MT5's Market Watch (brokers add suffixes: `EURUSD.r`, `XAUUSDm`).
- **The MetaTrader 5 phone app** on the same account, if they want push notifications.

## 2. Find MT5's data folder
`PY -m traderclaw find-mt5`. It lists each installation with its data folder, its install folder (from `origin.txt`)
and a ready `"export_dir": ...` line. If several show, ask which one they trade on. If none: ask them for MT5 > File >
Open Data Folder and the path it opens; `export_dir` = `<that folder>/MQL5/Files/traderclaw` (forward slashes).

## 3. Install the MT5 service (export, chart lines, phone push)
1. Ask, then copy `mt5/TraderClaw.mq5` to `<data folder>/MQL5/Services/TraderClaw.mq5`.
2. Compile it. MetaEditor silently ignores `/compile:` paths that contain spaces, so always run it **from the data
   folder with the relative path** `MQL5\Services\TraderClaw.mq5`. If no log appears, or the command is blocked, have
   the user do it (the reliable way):
   - **User:** in MT5 press F4 (Mac keyboard: Fn+F4) for MetaEditor, open Services > TraderClaw.mq5, press F7 (Fn+F7).
   - **Windows:** `powershell -NoProfile -Command "Set-Location '<data folder>'; & '<install folder>\metaeditor64.exe' /compile:MQL5\Services\TraderClaw.mq5 /log"`,
     then `powershell -NoProfile -Command "Get-Content -Encoding Unicode '<data folder>\MQL5\Services\TraderClaw.log' -Tail 3"`.
   - **macOS:** the data folder is normally the MT5 install folder itself (it holds `metaeditor64.exe`). With
     `P="$HOME/Library/Application Support/net.metaquotes.wine.metatrader5"`: `cd "<data folder>"`, then
     `WINEPREFIX="$P" "/Applications/MetaTrader 5.app/Contents/SharedSupport/wine/bin/wine" metaeditor64.exe /compile:MQL5\\Services\\TraderClaw.mq5 /log`.
     Exit code 1 is normal. Read the log: `iconv -f UTF-16LE -t UTF-8 MQL5/Services/TraderClaw.log | tail -3`.
     If the data folder has no `metaeditor64.exe`, use F7.
   The log (or MetaEditor's bottom panel) must say **0 errors**.
3. The user starts it: MT5 > View > Navigator (Ctrl+N) > Services > right-click **TraderClaw** > **Add Service** > OK.
   It runs in the background from then on, also after MT5 restarts.
4. Verify: `<export_dir>/status.txt` appears within 15 seconds and its `exported_server_time` moves.

## 4. Config
1. Copy `config.example.json` to `config.json`. Set `export_dir` (forward slashes), `symbols` (exact MT5 names) and
   `python_cmd` (`"py -3"` on Windows).
2. **Sessions are MT5 server hours.** Read `server_gmt_offset_hours` in `status.txt` and use the table in
   `docs/setup.md` ("Session hours"): most brokers are New York + 7 (2 in US winter, 3 in US summer), where the defaults
   fit. Otherwise compute the hours, and confirm them with the user in their own time zone.
3. `PY -m traderclaw once`. If it says "no candles yet ... run this again in 30 s", wait 30 s and run it again (MT5
   exports newly listed symbols at its next pass). It must end with `ok ... N symbols` for all their symbols; a symbol
   still missing after that has the wrong name.
4. `PY -m traderclaw status` and `PY -m traderclaw levels`. Ask the user to open an M15 chart of one symbol: amber
   lines labelled PDH, PDL, "Tokyo high"... should be there.

## 5. Phone alerts
- **MT5 push (default):** on the phone, the MetaTrader 5 app must be allowed to send notifications. In the app:
  Settings > Messages (or Chat and Messages): the 8-character MetaQuotes ID. In desktop MT5: Tools > Options >
  Notifications: tick "Enable Push Notifications", enter the ID, press Test. Then
  `PY -m traderclaw notify "TraderClaw test"` and ask whether it arrived (within about 10 s). If not: the `push=` line in
  `status.txt`, and `docs/troubleshooting.md`.
- **Telegram (optional):** the user runs `PY -m traderclaw telegram-setup` in their own terminal (the bot token is typed
  hidden; never ask for it, never open `~/.config/traderclaw/`). Then set `"push": {"mt5": true, "telegram": true}` and run
  `PY -m traderclaw telegram-test`.
- **Built-in alerts** (`config.json` "alerts"): a level taken, and how the next M15 closed (swept back inside or
  accepted beyond). Explain them and `families` (PW, PD, Session, PrevSession); switch on `session_open` if they want a
  push at each session's open.

## 6. Run it all the time
Ask first. Then:
- macOS: `bash scripts/macos/install-startup.sh`
- Windows: `powershell -ExecutionPolicy Bypass -File scripts/windows/install-startup.ps1` (no administrator needed)
- Linux (best effort): the systemd user unit in `docs/setup.md`, step 5.
Both scripts check that the engine started. Then `PY -m traderclaw status`: the engine log line is under a minute old.

## 7. TradingView (optional)
`docs/tradingview.md`: paste `tradingview/session_levels.pine` into the Pine editor; set "Broker server time = New York +"
and the session hours to match `config.json`.

## 8. Strategy and custom alerts (optional, recommended)
Offer the **strategy-interview** skill: it writes `my-strategy/STRATEGY.md` (private) and proposes alerts for the
mechanical parts, built with the **custom-alert** skill.

## 9. Journal and AI review
- The journal fills itself from MT5's history: `PY -m traderclaw journal`. Every new closed trade sends a 🧾 TRADE push.
- AI review: each review runs Claude Code headless and spends from their Claude plan or API credit, capped per run by
  `journal.review_budget_usd` (a one-trade review cost about $0.16 on Sonnet in testing); `review_model` picks the
  model. It needs the `claude` command installed and logged in. It judges against `my-strategy/STRATEGY.md`, or basic
  risk checks without one.
- **Ask** before a trial run. If they agree: `PY -m traderclaw review <id>` (an id from `journal`), then show them
  `journal/reviews.md`. If they want it after every trade: `"auto_review": true`.
- On macOS, if Claude Code was installed after step 6, run the install script again so the engine's PATH finds `claude`.

## Finish
Run the **health** skill. Summarise: what runs, where files are, which pushes they'll get, what must stay running
(MT5 logged in, the computer awake), and how to ask for changes ("alert me when...", "review my trades this week").
