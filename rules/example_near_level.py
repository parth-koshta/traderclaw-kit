"""Example rule: price comes within half an M15 ATR of an untaken previous-day or previous-week high/low. A heads-up
before a key level is reached, so you can be at the chart in time.

Copy this file to rules/<your_name>.py, change it, replay it, then set ENABLED = True.
"""

NAME = "Approaching a key level"
ENABLED = False
SYMBOLS = None
TIMEFRAME = "M5"
WATCH = ("PDH", "PDL", "PWH", "PWL")
DISTANCE_ATR = 0.5              # how close counts as "approaching", in M15 ATRs (ATR scales with volatility)


def check(ctx):
    atr = ctx.atr("M15")
    if not atr:
        return None
    sent = ctx.memory.setdefault("sent", [])
    msgs = []
    for lv in ctx.untaken():
        if lv.name not in WATCH:
            continue
        gap = abs(lv.price - ctx.price)
        key = f"{lv.name}:{ctx.fmt(lv.price)}"
        if gap <= DISTANCE_ATR * atr and key not in sent:
            sent.append(key)
            msgs.append(f"{ctx.fmt(ctx.price)} is {gap / atr:.1f} ATR from untaken {lv.name} {ctx.fmt(lv.price)}")
    del sent[:-20]
    return msgs
