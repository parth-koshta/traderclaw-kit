# TradingView levels

`tradingview/session_levels.pine` draws the same levels as MT5 on TradingView: previous weeks' highs and lows with
week start lines, PDH/PDL, yesterday's and today's session highs and lows (the running one dashed "(so far)"). Untaken
levels are amber; taken ones turn grey dotted and stop at the candle that took them.

## Add it

1. TradingView > **Pine Editor** (bottom panel) > open a new indicator, delete the template, paste the whole file.
2. **Save**, then **Add to chart**.
3. Settings (gear icon):
   - **Broker server time = New York +**: `7` for most MT5 brokers. Must match your MT5 server so days and sessions line up.
   - Session hours: the same server hours as `config.json`.
   - How many previous weeks, week start lines, colours.

Sessions show on 1h charts and below (a 4h candle spans two sessions); day and week levels on all timeframes.

## Prices differ a little

TradingView's feed isn't your broker's. On forex the difference is usually a fraction of a pip; on gold it can be tens
of cents on some feeds. Use a major FX feed (for example `FX:` or `OANDA:` symbols) and check exact levels on MT5,
where your trades fill. If lines don't appear and the indicator name shows three dots, it's still loading: reload the
tab before suspecting the script.
