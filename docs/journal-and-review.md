# Journal and AI reviews

## The journal fills itself

The engine reads MT5's deal history and keeps one row per closed trade in `journal/trades.csv` (and a readable
`journal/journal.md`). Partial closes count when the position is fully closed. Every account you log in to gets its
own history file, so the journal covers all of them.

- **R** = net result ÷ initial risk. The initial stop is the stop on the opening deal or, if you added it after opening,
  the first stop the engine saw (it checks every few seconds). No stop, no R: those trades count in money only.
- **Risk** in money uses MT5's tick value for the symbol.
- Net includes commission, swap and fees.

```bash
python3 -m traderclaw journal                       # update and show the latest 10
python3 -m traderclaw stats --days 30               # win rate, avg win/loss in R, expectancy; by symbol, session, setup, grade, weekday
python3 -m traderclaw journal tag <id> setup="Asia sweep" grade=B note="entered before the close"
```

The first run imports your existing history quietly; after that each closed trade sends a 🧾 TRADE push.

## AI reviews

Reviews need [Claude Code](https://code.claude.com/docs/en/setup) installed and logged in (a Claude subscription or API credit), even if you set the kit up another way. The engine finds it through its PATH: on a Mac, run `scripts/macos/install-startup.sh` again after installing Claude Code.

A review reads the trade's deals and the candles around it, checks it against `my-strategy/STRATEGY.md`, and writes:

```
### 2026-03-04 15:10 · XAUUSD sell · -1.00R (-25.00) · grade C
Facts: 0.02 lots, entry 2950.40, initial stop 2962.90, exit by stop at 2962.95 after 40 min; MFE +0.3R, MAE -1.0R.
Setup: none (the strategy's London sweep needs a sweep first; price was mid-range).
Good: risk within the limit · Bad: stop just under an obvious level; entry before any sweep · Rule breaks: none
Lesson: put the stop beyond the level price is heading for, or skip.
```

…to `journal/reviews.md`, tags the trade (setup, grade A/B/C), and sends a one-line push. Grades judge process, not
outcome: a loss taken by the plan is an A.

**Three ways to run it:**
1. **Ask:** in Claude Code, "review my trades today" (the review-trades skill), with a period summary.
2. **One command:** `python3 -m traderclaw review <id>`.
3. **Automatic:** `"journal": {"auto_review": true}` in `config.json`. The engine starts one headless Claude Code run
   (`claude -p`, prompt `prompts/review.md`) right after a trade closes. The run can read this folder and the MT5 export,
   write only in `journal/`, and run only the journal, candles, levels and notify commands. `review_model` picks the model,
   `review_budget_usd` caps each run (a one-trade review cost $0.16 on Sonnet in testing). Results and costs: `data/review-runs.csv`. A failed review isn't retried automatically (a retry costs money): you get one ⚙️ SYSTEM push a day, and `python3 -m traderclaw review` retries the failed ones.

Without a strategy file, reviews check the basics: a stop at entry, risk, reward to risk, stops moved against the trade,
and exits without a reason. With one, they check your own setups and rules, so writing it ("learn my strategy") makes
reviews far more useful.

## Notes

Tell your agent why you took or closed a trade ("journal this: ..."): it goes under that trade in `reviews.md` and the
review uses it.
