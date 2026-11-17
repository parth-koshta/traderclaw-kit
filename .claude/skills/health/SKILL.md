---
name: health
description: Check that the TraderClaw kit works end to end (MT5 service and export, engine, chart levels, push, rules, journal, AI review) and fix what doesn't. Use on "is it working", "no alerts", "lines missing", "check everything", or after setup or an update.
---

# Health check

`python3` below means `py -3` on Windows. Run in the kit folder.

1. `python3 -m traderclaw status`. Read every line: export folder found, service version, export age (OK or STALE),
   account, symbols with candles, `errors=`, push, rules (any BROKEN?), journal, engine log age (under a minute).
2. Fix the first problem with `docs/troubleshooting.md` (symptom → cause → fix), then run status again. What only the
   user can do (MT5 clicks, phone settings), tell them exactly.
3. `python3 -m traderclaw once`: ends with `ok ... N symbols` for every configured symbol.
4. Lines: the export folder's `draw_levels.csv` has rows; ask the user to check an M15 chart.
5. Push: `python3 -m traderclaw notify "health check"`; ask whether it arrived within about 10 seconds.
6. Rules: `python3 -m traderclaw replay rules/<name>.py --days 2` for each enabled rule runs without errors.
7. AI review (only if `auto_review` is on): the last rows of `data/review-runs.csv` say `success`; anything parked in
   `data/review_failed.json`? Don't start a paid review without asking.
8. `python3 -m unittest discover -s tests` passes.

Report: each part OK or not, what you fixed, and anything the user must do.
