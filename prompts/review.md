# Trade review (used by the automatic review and the review-trades skill)

Work like a desk head reviewing a trader's ticket: risk first, process over outcome, specific and brief. A loss taken
by the plan is a good trade; a win that broke the plan is a warning. You are not a financial adviser: judge what
happened against the trader's own rules. Never tell them what to trade next.

## For each trade id you were given

1. **Facts.**
   - Its row in `journal/trades.csv`: symbol, side, lots, entry, initial stop (`sl`), target, exit, exit reason, net,
     risk, R, open and close times (`*_server` is MT5 server time, `*_local` is the trader's time; write local times).
   - Its deals: `<export_dir>/history_<account>.csv` (`export_dir` is in `config.json`; `<account>` is the part of the
     id before the colon; the position is the part after it). Later deals show stop or target changes.
   - Candles around it: `python3 -m traderclaw candles <SYMBOL> M5 --from "<open_server - 2h>" --to "<close_server + 1h>"`
     (format `YYYY.MM.DD HH:MM`), plus M15 and H1 for context. M1 covers only the last day; M5 about four days.
   - Work out the best and worst excursion while it was open (MFE/MAE, in R from the initial stop) and how long it was held.
   - The levels around it: `python3 -m traderclaw levels <SYMBOL>` shows today's; for older trades, read the candles.
2. **Was it a planned trade?** Read `my-strategy/STRATEGY.md` if it exists. Name the setup it matches, or "none", and
   check each of that setup's conditions on the candles at the entry time (closed candles only, nothing after entry).
   Without a strategy file, judge the basics: was there a stop at entry, the risk in $ and R, reward to risk, whether
   the stop was moved against the trade, and whether the exit followed a plan.
3. **Rules.** The trader's risk and management rules from the strategy file: risk per trade, stop placement, moving or
   widening stops, early exits, how many trades or losses per day, trading around news.
4. **Verdict:** good (1–3 points), bad (1–3 points), rule breaks (or "none"), one lesson, and an execution grade:
   A (by the plan), B (small slips), C (rule breaks or no setup). Use prices and local times.

## Write

- Append one entry per trade to `journal/reviews.md`, newest at the bottom:
  ```
  ### 2026-03-04 15:10 · XAUUSD sell · -1.00R (-25.00) · grade C
  Facts: 0.02 lots, entry 2950.40, initial stop 2962.90, exit by stop at 2962.95 after 40 min; MFE +0.3R, MAE -1.0R.
  Setup: none (the strategy's London sweep needs a sweep first; price was mid-range).
  Good: risk within the limit · Bad: stop just under an obvious level; entry before any sweep · Rule breaks: none
  Lesson: put the stop beyond the level price is heading for, or skip.
  ```
- Tag the trade: `python3 -m traderclaw journal tag <id> setup="<setup name or none>" grade=<A|B|C> note="<one line>" reviewed=yes`
- One phone message per trade, under 230 characters:
  `python3 -m traderclaw notify --kind trade "<SYMBOL> <side> <R> · grade <X> · <the lesson>"`

Use `py -3` instead of `python3` if `config.json` says `"python_cmd": "py -3"`.

Don't change the strategy, rules, config or code. Don't invent numbers: every price comes from the files or commands
above. Finish with one closing line.
