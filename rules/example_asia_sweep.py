"""Example rule: during London, price runs the Tokyo (Asia) session's high or low, then an M5 candle closes back inside
the range. A classic "liquidity sweep" pattern, here only as an example of the rule API: it's a heads-up to look at
the chart, not a trade signal.

Copy this file to rules/<your_name>.py (your own rules stay out of git), change it, replay it, then set ENABLED = True.
"""

NAME = "Asia range swept in London"
ENABLED = False                 # examples are off; in your copy, set True once the replay looks right
SYMBOLS = None                  # None = every symbol in config.json
TIMEFRAME = "M5"                # check() runs after each M5 candle closes


def check(ctx):
    if not ctx.in_session("London"):
        return None
    asia = ctx.session("Tokyo")                     # (high, low) of today's Tokyo session
    bar = ctx.last("M5")
    if not asia or not bar:
        return None
    high, low = asia
    done = ctx.memory.setdefault("done", [])        # remember what already fired today
    day = ctx.now.strftime("%Y-%m-%d")
    msgs = []
    if bar.h > high and bar.c < high and f"{day}:high" not in done:
        done.append(f"{day}:high")
        msgs.append(f"Tokyo high {ctx.fmt(high)} swept to {ctx.fmt(bar.h)}, M5 closed back below at {ctx.fmt(bar.c)} "
                    f"({ctx.local(bar.t)})")
    if bar.l < low and bar.c > low and f"{day}:low" not in done:
        done.append(f"{day}:low")
        msgs.append(f"Tokyo low {ctx.fmt(low)} swept to {ctx.fmt(bar.l)}, M5 closed back above at {ctx.fmt(bar.c)} "
                    f"({ctx.local(bar.t)})")
    del done[:-10]
    return msgs
