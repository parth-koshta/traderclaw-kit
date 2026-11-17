# Custom alert rules

One Python file per rule. Your own rules (every file here except this README and `example_*.py`) are git-ignored, so
your strategy never gets published. Ask your agent: *"alert me when ..."* (the custom-alert skill), or write one yourself.

## A rule file

```python
NAME = "London sweep of the Tokyo low"   # shown in the push: "EURUSD · London sweep of the Tokyo low: <message>"
ENABLED = True                           # False keeps the file but doesn't run it
SYMBOLS = ["EURUSD", "GBPUSD"]           # None = every symbol in config.json
TIMEFRAME = "M5"                         # check() runs once after each candle of this timeframe closes

def check(ctx):
    ...
    return "message"                     # or a list of messages, or None for nothing
```

- The engine calls `check(ctx)` right after each `TIMEFRAME` candle closes, for each symbol. Each message is pushed once.
- `ctx` sees only what existed at that close, in live runs and replays alike, so a replay shows what you'd really have got.
- When the engine starts, it skips the first candle it sees, so a restart never fires old alerts.
- If `check` raises an error, you get one ⚙️ SYSTEM push a day for that rule, and it keeps being tried.

## What `ctx` gives you

| | |
|---|---|
| `ctx.symbol`, `ctx.now` | the symbol; the close time being checked (server time, a `datetime`) |
| `ctx.bars(tf, n=None)` | closed candles, oldest first; each has `.t` (open time), `.o .h .l .c`, `.v` (tick volume) |
| `ctx.last(tf)` | the last closed candle (or None) |
| `ctx.price` | the latest closed price |
| `ctx.atr(tf="M15", n=14)` | average true range: use it for distances ("within 0.5 ATR"), never fixed pips |
| `ctx.swing_highs(tf, n=2, lookback=100)` / `ctx.swing_lows(...)` | `[(time, price), ...]`: candles higher (lower) than the n on each side |
| `ctx.levels` | every chart level: `.name` ("PDH", "Prev London low", "Tokyo high"), `.price`, `.side` ("high"/"low"), `.taken_at`, `.running` |
| `ctx.level("PDL")` | one level by name (None if it doesn't exist yet) |
| `ctx.untaken(side=None)` | untaken finished levels, nearest to the price first |
| `ctx.session("London", days_ago=0)` | `(high, low)` of a session from config.json, today so far or an earlier day |
| `ctx.in_session("London")` | is `now` inside that session? |
| `ctx.hour`, `ctx.minute` | server time |
| `ctx.local(t=None)` | a time as HH:MM on your computer's clock, for messages |
| `ctx.fmt(price)` | a price with the symbol's digits |
| `ctx.memory` | a dict kept between checks (per rule and symbol): use it for "only once a day" |
| `ctx.positions` | your open positions on this symbol (live only): `ticket, type, volume, price_open, sl, tp, profit` |
| `ctx.live` | False during a replay |

Times: the candles are in MT5 server time. Sessions in config.json are server hours too.

## Test before switching on

```bash
python3 -m traderclaw replay rules/my_rule.py --days 3          # what it would have sent, and when
python3 -m traderclaw replay rules/my_rule.py --days 10 --symbol EURUSD
```

A replay can only go back as far as MT5 exports: M1 about 1 day, M5 about 4 days, M15 about 10 days, H1 about a month.
For a rule that must stay correct, add a test in `tests/test_rule_<name>.py` (git-ignored, like the rule).

## Rules are alerts, not trades

A rule can only send a message. The kit can't place, change or close trades, and a test (`tests/test_kit.py`,
`ReadOnlyTest`) fails if anyone adds trading calls.
