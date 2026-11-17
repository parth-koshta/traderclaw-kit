---
name: strategy-interview
description: Learn the user's trading strategy by interviewing them, write it to my-strategy/STRATEGY.md, and propose custom alerts for its mechanical parts. Use on "learn my strategy", "here's how I trade", "set up alerts for my strategy", or when reviews need a strategy file.
---

# Strategy interview

`python3` in the commands below means `py -3` on Windows (`python_cmd` in config.json). Run them in the kit folder.

Read `AGENTS.md` first. The goal: a strategy file precise enough that a review can check a trade against it and a rule
can alert on it. You record their strategy; you don't invent or improve one, and you give no financial advice.

## 1. Interview
Ask a few questions at a time (use the question tool if you have one), in the order of
`my-strategy/STRATEGY.template.md`: markets and hours, how they decide bias, the levels they watch, each setup, risk,
trade management. For each setup push for checkable answers:
- "price sweeps the low" → which low (PDL, Tokyo low, a swing low on which timeframe), and how far through counts?
- "then it shifts" → which candle closes where, on which timeframe?
- "I enter" → market or limit, where exactly; stop where; target where?
- "only in London" → which hours, in their time zone (convert to server time with `status.txt`'s offset)?

Use their own words for names. If they share screenshots of past trades, ask what they saw at each step and turn that
into conditions. Mark anything still vague `[ASK]` rather than guessing.

## 2. Write it
Copy the template to `my-strategy/STRATEGY.md` (git-ignored: it never leaves their computer) and fill it in. Read it
back to them in short form and fix what they correct.

## 3. Check it against their history (if they have trades)
`python3 -m traderclaw journal` and `stats`. For a few recent trades, say which setup each looks like, using the candles
(`python3 -m traderclaw candles ...`). This often shows a rule they follow but didn't mention: add it with their OK.

## 4. Propose alerts
List the parts a machine can check on closed candles (levels taken, a sweep and close back inside, a session window, an
ATR distance). Leave out judgement calls; say so. For each alert they want, run the **custom-alert** skill. Phrase
alerts as "look at the chart now" heads-ups, not instructions to trade.

## 5. Reviews
Tell them the AI review (`prompts/review.md`) now grades trades against this file. Offer to switch on
`journal.auto_review` (setup skill, step 9, explains the cost).

Keep `STRATEGY.md` current: whenever they change a rule, rewrite the affected section, change any rule file that
depends on it (and replay it), and say what changed.
