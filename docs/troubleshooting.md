# Troubleshooting

Start with `PY -m traderclaw status` (PY = `py -3` on Windows, `python3` on Mac/Linux), in the kit folder. Fix the first
problem it shows, then run it again.

| Symptom | Likely cause | Fix |
|---|---|---|
| `'python3' is not recognized`, or the Microsoft Store opens | Windows: Python not installed, or not on PATH | install from python.org with "Add python.exe to PATH" ticked; use `py -3` |
| `No module named traderclaw` | the terminal isn't in the kit folder | `cd` into the folder that holds `README.md` and `traderclaw/` (a ZIP can unpack into two nested folders) |
| `config.json isn't valid JSON (line N ...)` | a missing comma or quote, or `\` in a Windows path | fix that line; write paths with `/` |
| Compile errors in MetaEditor | an old MT5 build, or the file got changed | update MT5 (Help > Check for updates); copy `mt5/TraderClaw.mq5` again |
| No **TraderClaw** under Services | not compiled, or copied into the wrong folder | it must be in the data folder's `MQL5/Services/` (File > Open Data Folder); compile it (step 1) |
| `export_dir ... NOT FOUND`, or "no status.txt" | the service isn't running, or the wrong data folder | Navigator > Services > right-click TraderClaw > Start; check `export_dir` with `find-mt5` |
| `STALE` | MT5 closed or disconnected, the computer slept, or it's the weekend | open MT5 and log in; on weekdays the engine also sends a ⚙️ SYSTEM push when it goes stale |
| `no candles yet for X` | just added (wait 30 s), or the wrong name | use the exact Market Watch name, suffix included; the symbol must be in Market Watch |
| `errors=` in `status.txt` | the service's own problems | "symbol not found": the name; FileOpen/FileMove: an antivirus or another program locking the folder |
| No lines on the chart | engine not running; a chart of an unlisted symbol; H4/D1 chart (sessions show only up to H1) | `status`; `draw_levels.csv` in the export folder should have rows; use an M1-H1 chart of a listed symbol |
| Session lines at the wrong hours | session hours don't match your broker's server time | docs/setup.md, "Session hours" |
| Push never arrives | phone notifications off, wrong MetaQuotes ID, MT5 notifications not enabled | step 6 of setup; the `push=` line in `status.txt`; MT5's Test button must work first |
| Engine log is old / "the engine hasn't run" | the startup job isn't running | Mac: `launchctl list \| grep traderclaw` and `data/engine.err.log`; Windows: Task Scheduler > "TraderClaw engine" (or the Startup folder shortcut); run `PY -m traderclaw once` to see the error |
| Mac: the engine dies right after starting | the kit is in Documents, Desktop, Downloads or iCloud | move it to `~/traderclaw-kit` and run `scripts/macos/install-startup.sh` again |
| A rule shows `BROKEN` | a Python error in that rule | run `PY -m traderclaw replay rules/<name>.py` to see it; fix it (or ask your agent) |
| "AI review failed" push | `claude` not installed, not logged in, or not on the engine's PATH; budget too small | run `PY -m traderclaw review` in a terminal to see it; `data/review-runs.csv`, `data/reviews/*.err`; Mac: re-run the install script after installing Claude Code |
| Journal stopped updating (Windows) | `journal/trades.csv` is open in Excel | close it; the journal catches up on the next loop |
| Journal is missing an account | MT5 writes each account's history only while logged in to it | log in to that account in MT5 for a minute |

Still stuck: `data/engine.log` has the engine's messages. If you use an AI agent, ask it to "check everything" (the
health skill).
