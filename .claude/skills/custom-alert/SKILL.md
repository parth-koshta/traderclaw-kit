---
name: custom-alert
description: Create, change or remove a custom phone alert as a rule file in rules/, replay it on past candles, and switch it on. Use on "alert me when...", "notify me if...", "add an alert", "change/stop the ... alert".
---

# Custom alert

`python3` in the commands below means `py -3` on Windows (`python_cmd` in config.json). Run them in the kit folder.

Read `AGENTS.md` and `rules/README.md` first (the rule API). A rule only sends messages; it never trades.

## 1. Pin the condition down
Restate it as something checkable on closed candles: which symbols, which timeframe closes, which level or pattern,
how far (in ATR, not fixed pips), during which hours (server time), and how often (once per day? per level?). Ask when
any part is vague. If it's one of the built-in alerts (a level taken, how the M15 closed after it, session opens), switch
that on in `config.json` "alerts" instead of writing a rule.

## 2. Write the rule
Copy the closest `rules/example_*.py` to `rules/<short_name>.py` (git-ignored). Set NAME, SYMBOLS, TIMEFRAME and
ENABLED = False while testing. Keep it simple; use `ctx.memory` for "only once". Messages say what happened with prices
and `ctx.local()` times, e.g. "Tokyo low 1.08410 swept to 1.08385, M5 closed back above at 14:35".

## 3. Prove it
- `python3 -m traderclaw replay rules/<name>.py --days 4` (and `--days 10` for M15 or slower rules).
- Check two or three hits against the candles yourself (`python3 -m traderclaw candles ...`), and look for a day where
  it should have fired but didn't. Show the user the list and ask if that's what they want. Too many hits? Tighten it.
- For anything non-trivial, add `tests/test_rule_<name>.py` with synthetic candles (see `tests/test_kit.py`
  `make_bars`), and run `python3 -m unittest discover -s tests`.

## 4. Switch it on
Set ENABLED = True. The running engine picks it up within a loop (no restart). `python3 -m traderclaw status` lists it.
Say when they should expect the first alert, and that a broken rule sends one ⚙️ SYSTEM push a day.

## Changing or removing
Edit the file and replay again, or set ENABLED = False, or delete it. If the rule implements part of
`my-strategy/STRATEGY.md`, keep the two consistent.
