# Setup by hand

An AI agent does all of this when you say "set me up" (`.claude/skills/setup/SKILL.md` is the same procedure, written
for it). By hand it takes about 30 minutes. Stuck at any step: [troubleshooting.md](troubleshooting.md).

In the commands below, **`PY`** means `py -3` on Windows and `python3` on macOS/Linux.

## 0. Before you start

You need:
- **MetaTrader 5 desktop**, installed and logged in to your account (a demo is fine). Windows: from your broker or
  metatrader5.com. Mac: the official MetaTrader 5 app. (Linux under Wine works, best effort.)
- **The MetaTrader 5 phone app**, logged in to the same account, for push notifications.
- **Python 3.9 or newer.** Windows: python.org > Downloads; in the installer tick **"Add python.exe to PATH"** and keep
  "py launcher" ticked. Check: `py -3 --version`. Mac: `python3 --version` in Terminal (if it's missing, macOS offers to
  install it, or use python.org).
- **This folder.** Either `git clone https://github.com/parth-koshta/traderclaw-kit` or, without Git, the green
  **Code > Download ZIP** button on GitHub, then unzip. A ZIP unpacks to `traderclaw-kit-main`, sometimes inside a
  second folder of the same name: use the one that contains `README.md` and the `traderclaw` folder.
  - Mac: put it in your home folder (`~/traderclaw-kit`), **not** in Documents, Desktop, Downloads or iCloud Drive,
    which macOS blocks for programs running in the background.

**A terminal in the folder:** Windows: open the folder in File Explorer, click the address bar, type `powershell`, press
Enter. Mac: open Terminal, type `cd ~/traderclaw-kit` (or `cd ` and drag the folder onto the window), press Enter.

**Editing `config.json`:** Windows: right-click > Open with > Notepad. Mac: TextEdit, after Format > Make Plain Text (or
any code editor). Keep the quotes and commas exactly as in the example.

**What has to stay running:** MT5 (open and logged in) and the engine (step 5 makes it start by itself), on a computer
that's awake. Closed MT5 or a sleeping laptop means no lines, alerts or journal updates until it's back. One kit covers
one MT5 installation: the one whose data folder you choose in step 2.

## 1. Install the MT5 service

1. In MT5: **File > Open Data Folder**. Copy `mt5/TraderClaw.mq5` from this kit into that folder's `MQL5/Services/`.
2. In MT5 press **F4** (on a Mac keyboard: **Fn+F4**) to open MetaEditor. In its Navigator, open
   **Services > TraderClaw.mq5** and press **F7** (Fn+F7), or click Compile. The bottom panel must say **0 errors**.
3. Back in MT5: **View > Navigator** (Ctrl+N), expand **Services**, right-click **TraderClaw** > **Add Service**. In the
   window that opens, keep the defaults and press OK. It starts, and restarts with MT5 from now on.
4. Check: within 15 seconds a `traderclaw` folder appears in the data folder's `MQL5/Files/`, with `status.txt` in it.

The service only reads from MT5. It exports candles (M1 to D1), prices, your open positions and orders, account
figures and deal history; draws the lines listed in `draw*.csv`; and sends the messages in `notify.tsv` as push
notifications. It has no trading functions at all.

## 2. Find your export folder

```
PY -m traderclaw find-mt5
```

It lists each MT5 installation and prints a ready line for config.json, for example
`"export_dir": "C:/Users/you/AppData/Roaming/MetaQuotes/Terminal/ABC123/MQL5/Files/traderclaw",`.
Use **forward slashes** (`/`) in the path, also on Windows: backslashes break the file.

## 3. Configure

1. Copy `config.example.json` to `config.json` (Windows: `copy config.example.json config.json`; Mac:
   `cp config.example.json config.json`).
2. Open `config.json` and set:
   - `export_dir`: the line from step 2.
   - `symbols`: your symbols, **exactly** as in MT5's Market Watch (some brokers add suffixes: `EURUSD.r`, `XAUUSDm`).
   - `python_cmd`: `"py -3"` on Windows (leave `"python3"` on Mac/Linux).
   - `sessions`: see below.
3. Run:
   ```
   PY -m traderclaw once
   ```
   The first time, it may say "no candles yet ... run this again in 30 s": MT5 only starts exporting newly listed
   symbols at its next export. Wait 30 seconds and run it again. It should print `ok ... N symbols`.
4. `PY -m traderclaw status` and `PY -m traderclaw levels`. Then open an M15 chart of one of your symbols: amber
   lines labelled PDH, PDL, "Tokyo high" and so on should be there.

### Session hours

Sessions are in **MT5 server time** (your broker's clock, shown in Market Watch). Look at `server_gmt_offset_hours` in
`status.txt` (in your export folder) and match your broker:

| `server_gmt_offset_hours` | Your broker | Tokyo | London | New York |
|---|---|---|---|---|
| 2 from Nov to mid-Mar, 3 the rest of the year | New York + 7, the most common (the defaults) | 3-10 | 10-15 | 15-24 |
| 2 all year | GMT+2, no US daylight saving: in US summer (mid-Mar to early Nov) use → | 2-9 | 9-14 | 14-23 |
| 0 all year | GMT: in US winter use → / in US summer use → | 1-8 / 0-7 | 8-13 / 7-12 | 13-22 / 12-21 |

The defaults are Tokyo 20:00-03:00, London 03:00-08:00 and New York 08:00-17:00 New York time. For any other broker,
add (server time − New York time) to those hours. With a broker that doesn't follow US daylight saving, change the hours
when the US clocks change. A session can't cross server midnight. Check them against your own clock: London's
session should start at the London open.

## 4. Settings reference (`config.json`)

| Setting | What it does |
|---|---|
| `export_dir` | the export folder (step 2) |
| `python_cmd` | how to run Python here: `"python3"` or `"py -3"` (used by the AI review's commands) |
| `symbols` | the symbols to export and analyse; MT5 picks up changes within 15 s |
| `sessions` | `name`, `from`, `to` in server hours (above) |
| `levels` | which levels to draw: `previous_week`, `previous_day`, `previous_day_sessions`, `today_sessions` (true/false) |
| `alerts.level_taken` | push when a level is traded through for the first time |
| `alerts.close_after_take` | push how the next M15 candle closed: back inside (a sweep) or beyond (accepted) |
| `alerts.families` | which levels alert: `"PW"` (last week), `"PD"` (yesterday), `"Session"` (today's), `"PrevSession"` (yesterday's) |
| `alerts.session_open` | push at each session's open with the nearest untaken levels above and below |
| `push.mt5`, `push.telegram` | where notifications go (step 6) |
| `journal.enabled` | keep the journal from MT5's history |
| `journal.account_labels` | names for your accounts, e.g. `{"Broker-Live_1234": "Live"}` (the key is `account_key` in `status.txt`) |
| `journal.auto_review` | AI-review each trade after it closes (needs Claude Code; costs money; off by default) |
| `journal.review_model`, `journal.review_budget_usd` | the model for reviews, and the most one review run may spend |
| `loop_seconds` | how often the engine runs (default 15) |
| `stale_after_seconds` | when the export counts as stale (default 180) |

Changes apply within one loop; no restart needed.

## 5. Keep it running

- **Windows:** in the PowerShell window from step 0:
  `powershell -ExecutionPolicy Bypass -File scripts/windows/install-startup.ps1`. No administrator needed. It starts the
  engine now and at every logon, and checks it runs.
- **Mac:** `bash scripts/macos/install-startup.sh`. Same: starts now and at every login, and checks it runs.
- **Linux (best effort):** a systemd user service, `~/.config/systemd/user/traderclaw.service`:
  ```
  [Service]
  WorkingDirectory=/home/you/traderclaw-kit
  ExecStart=/usr/bin/python3 -m traderclaw run
  Environment=PATH=/home/you/.local/bin:/usr/local/bin:/usr/bin
  Restart=always
  [Install]
  WantedBy=default.target
  ```
  then `systemctl --user enable --now traderclaw`. The PATH must include the folder with `claude` for AI reviews.

`PY -m traderclaw status` shows the engine's last log line; it should be less than a minute old.

## 6. Phone notifications

**MetaTrader app (default):**
1. On your phone, open the MetaTrader 5 app and allow it to send notifications (phone Settings > Notifications).
2. In the app: **Settings > Messages** (on some versions "Chat and Messages"): note your **MetaQuotes ID** (8 characters).
3. In desktop MT5: **Tools > Options > Notifications**: tick **Enable Push Notifications**, type the ID, press **Test**.
   A test message should reach the phone.
4. `PY -m traderclaw notify "hello"`: it should arrive within about 10 seconds. If not, the `push=` line in `status.txt`
   says why ([troubleshooting.md](troubleshooting.md)).

**Telegram (optional):** `PY -m traderclaw telegram-setup`, follow the prompts (create a bot with @BotFather; the token
is typed hidden and saved in `~/.config/traderclaw/telegram.env`, never in this folder), set
`"push": {"mt5": true, "telegram": true}`, then `PY -m traderclaw telegram-test`.

## 7. Optional

- **TradingView:** [tradingview.md](tradingview.md).
- **Your strategy and custom alerts:** with Claude Code, say "learn my strategy", then "alert me when ...". By hand:
  [../rules/README.md](../rules/README.md).
- **Journal and AI reviews:** [journal-and-review.md](journal-and-review.md). The journal works without any AI; reviews
  need Claude Code.
- **Updating or removing the kit:** [update-and-uninstall.md](update-and-uninstall.md).
