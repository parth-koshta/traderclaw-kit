---
name: review-trades
description: Review the user's closed trades and keep the journal - per-trade AI reviews, notes, and period summaries (win rate, R, expectancy, rule breaks, patterns). Use on "review my trades", "how did I do today/this week", "journal this", "why do I keep losing", "weekly review".
---

# Review trades and journal

`python3` in the commands below means `py -3` on Windows (`python_cmd` in config.json). Run them in the kit folder.

Read `AGENTS.md` first. Judge process over outcome, against the user's own `my-strategy/STRATEGY.md`. No advice on
future trades beyond lessons from their own rules.

## Steps
1. **Update:** `python3 -m traderclaw journal` (imports MT5's history). Check `python3 -m traderclaw status`: each
   account's history only updates while MT5 is logged in to it, so say how fresh the data is.
2. **Unreviewed trades in the period:** rows in `journal/trades.csv` with an empty `reviewed`. Review each by following
   `prompts/review.md` exactly (it writes `journal/reviews.md`, tags the trade, and may push a summary; ask whether
   they want pushes for a batch). For many trades, review the ones with rule-relevant events first and summarise the rest.
3. **Their own notes:** if they tell you why they took or closed a trade, add it under that trade's entry in
   `journal/reviews.md` as "Trader's note (time): ...", and use it in the verdict.
4. **Numbers:** `python3 -m traderclaw stats --days N` (by symbol, session, setup, grade, weekday). Every number you
   report comes from this output or the files, not estimates. Under ~30 trades in a group, call it a hint.
5. **Patterns:** what the reviews keep finding (same rule break, same session, stops too tight...). Offer to add a lesson
   to `my-strategy/STRATEGY.md` section 6, only with their OK.

## Report
A short table (trades, win rate, average win and loss in R, expectancy, net), the rule breaks with dates, the grades,
then one or two lessons. End by saying the decisions are theirs.
