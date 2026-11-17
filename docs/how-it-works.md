# How it works

## The pieces

1. **The MT5 service** (`mt5/TraderClaw.mq5`) runs inside MetaTrader 5 in the background. Every 15 seconds, and right
   after each minute closes, it writes the export folder (`MQL5/Files/traderclaw/`). Every 5 seconds it redraws any chart
   whose `draw*.csv` changed, and it pushes new lines of `notify.tsv` to your phone (one every 7 seconds at most: MT5's limit).
   Stopping or removing the service removes its lines; starting it draws them again.
2. **The engine** (`python3 -m traderclaw run`) loops every `loop_seconds`. Each pass:
   - checks the export is fresh (a ⚙️ SYSTEM push if it's been stale for a while on a weekday),
   - computes the levels per symbol and writes `draw_levels.csv`,
   - sends the built-in level alerts,
   - runs your rules in `rules/` on each newly closed candle,
   - updates the journal from the deal history, pushes a 🧾 TRADE line per newly closed trade, and queues it for review,
   - starts or finishes the background AI review.
3. **Your agent** (Claude Code, or another) sets things up, writes your strategy file and rules, and reviews trades,
   using the same commands you can run.

## Time

MT5 files use **server time** (your broker's clock). Sessions in `config.json` are server hours. Pushes, the journal's
`*_local` columns and `ctx.local()` use your computer's clock. `status.txt` has `server_gmt_offset_hours`.

## The levels

| Name | What | Shown on |
|---|---|---|
| PWH / PWL | last week's high / low (server Monday 00:00 to Friday close) | M1-D1 |
| PDH / PDL | the previous day's high / low (the broker's D1 candle) | M1-D1 |
| Prev Tokyo/London/NY high/low | yesterday's session highs and lows | M1-H1 |
| Tokyo/London/NY high/low | today's: finished ones solid, the running one dashed "(so far)" | M1-H1 |

A level is **taken** at the first trade beyond it after it formed: the line then turns grey dotted and stops at that
candle. Levels at the same price share one line ("PWL · PDL · Prev NY low 1.11310").

## Built-in alerts (`config.json` "alerts")

| Setting | Push |
|---|---|
| `level_taken` | 💧 LEVEL "EURUSD took PDL 1.08410 at 14:32" |
| `close_after_take` | 💧 LEVEL "... the 14:30 M15 candle closed back above it (swept, not accepted)" or "closed below it (accepted)" |
| `session_open` | 🕒 SESSION at each session's open: the nearest untaken levels above and below |
| `families` | which levels alert: `PW`, `PD`, `Session` (today), `PrevSession` (yesterday's) |

Only events from the last 30 minutes alert, so a restart never replays old ones.

## Export files

| File | Columns / content |
|---|---|
| `status.txt` | `exported_server_time`, `exported_gmt_time`, `server_gmt_offset_hours`, `account_key`, `account_company`, `symbols`, `service_version`, `push`, `errors` |
| `<SYM>_<TF>.csv` (M1 M5 M15 H1 H4 D1) | `time,open,high,low,close,tick_volume,spread`; oldest first; the last row is still forming |
| `quotes.csv` | `symbol,bid,ask,spread_points,digits,point,tick_value,tick_size,contract_size,tick_time` |
| `positions.csv` | `ticket,symbol,type,volume,price_open,sl,tp,price_current,profit,swap,time_open` |
| `orders.csv` | `ticket,symbol,type,volume,price,sl,tp,time_setup` |
| `account.csv` | `company,server,account_key,currency,balance,equity,profit,margin,margin_free` |
| `history_<account_key>.csv` | every deal: `deal,position,time,symbol,type,entry,volume,price,sl,tp,profit,commission,swap,fee,reason,comment` |
| `draw*.csv` (engine → service) | `version,<n>` then `symbol,type,name,time1,price1,time2,price2,color,style,width,timeframes,text` |
| `notify.tsv` (engine → service) | `id\ttime\ttext`; the service pushes each new id once |
| `symbols.txt` (engine → service) | the symbols to export, from `config.json` |

`account_key` is `<server>_<last 4 digits of the login>`, so each account's history has its own file.

## Adding your own drawings

Any `draw_<name>.csv` in the export folder is drawn too (objects named `TCK_draw_<name>.`, so your own drawings are never
touched). Write it with `traderclaw.draw.write_file(export_dir, "draw_<name>.csv", rows)`, which handles the version.
