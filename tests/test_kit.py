"""Tests on synthetic candles and deals (no market data in the repo). Run: python3 -m unittest discover -s tests"""
import glob
import json
import os
import re
import sys
import tempfile
import unittest
from datetime import datetime, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from traderclaw import alerts, draw, journal, notify, rules  # noqa: E402
from traderclaw.config import DEFAULTS, ConfigError, load  # noqa: E402
from traderclaw.data import Bar, SymbolInfo, closed  # noqa: E402
from traderclaw.levels import chart_levels, find  # noqa: E402

SESSIONS = DEFAULTS["sessions"]
EURUSD = SymbolInfo("EURUSD", 5, 0.00001, 1.1, 1.1, tick_value=1.0, tick_size=0.00001)


def aggregate(m5, minutes):
    out = {}
    for b in m5:
        k = b.t - timedelta(minutes=(b.t.hour * 60 + b.t.minute) % minutes) if minutes < 1440 else \
            datetime(b.t.year, b.t.month, b.t.day)
        if k not in out:
            out[k] = Bar(k, b.o, b.h, b.l, b.c)
        else:
            x = out[k]
            x.h, x.l, x.c = max(x.h, b.h), min(x.l, b.l), b.c
    return [out[k] for k in sorted(out)]


def make_bars(spec, start=datetime(2026, 11, 9)):
    """spec: {(day, hour): (high, low)} on a flat 1.1000 market; every M5 bar from `start` for 3 days."""
    m5 = []
    t = start
    while t < start + timedelta(days=3):
        h, l = spec.get(((t - start).days, t.hour), (1.1005, 1.0995))
        m5.append(Bar(t, 1.1000, h, l, 1.1000))
        t += timedelta(minutes=5)
    return {"M5": m5, "M15": aggregate(m5, 15), "H1": aggregate(m5, 60), "D1": aggregate(m5, 1440),
            "M1": [], "H4": aggregate(m5, 240)}


class LevelsTest(unittest.TestCase):
    def test_previous_day_sessions_and_taken(self):
        # Monday: London (10-15) makes the day's high 1.1050, Tokyo (03-10) the low 1.0950.
        bars = make_bars({(0, 11): (1.1050, 1.0995), (0, 4): (1.1005, 1.0950),
                          (1, 12): (1.1060, 1.0995)})       # Tuesday 12:00 takes Monday's high
        now = datetime(2026, 11, 10, 13, 0)
        lv = chart_levels(bars, now, SESSIONS)
        pdh, pdl = find(lv, "PDH"), find(lv, "PDL")
        self.assertEqual((pdh.price, pdl.price), (1.1050, 1.0950))
        self.assertEqual(pdh.taken_at, datetime(2026, 11, 10, 12, 0))
        self.assertIsNone(pdl.taken_at)
        self.assertEqual(find(lv, "Prev London high").price, 1.1050)
        self.assertTrue(find(lv, "London high").running)       # today's London is still running at 13:00
        self.assertEqual(find(lv, "London high (so far)").price, 1.1060)

    def test_nothing_after_now_is_seen(self):
        bars = make_bars({(1, 14): (1.1100, 1.0995)})          # a spike at 14:00 on Tuesday
        lv = chart_levels(bars, datetime(2026, 11, 10, 13, 0), SESSIONS)
        self.assertIsNone(find(lv, "PDH").taken_at)
        self.assertLess(find(lv, "London high").price, 1.1100)
        # A candle opening exactly at `now` has no prices yet (replays evaluate at candle closes).
        lv = chart_levels(bars, datetime(2026, 11, 10, 14, 0), SESSIONS)
        self.assertLess(find(lv, "London high").price, 1.1100)


class DrawTest(unittest.TestCase):
    def test_same_price_levels_share_a_line(self):
        bars = make_bars({(0, 11): (1.1050, 1.0995)})
        now = datetime(2026, 11, 10, 9, 0)
        lv = chart_levels(bars, now, SESSIONS)
        rows = draw.level_rows({"EURUSD": lv}, {"EURUSD": EURUSD}, now, {"EURUSD": 0.00002})
        texts = [r.split(",")[11] for r in rows]
        self.assertIn("PDH · Prev London high 1.10500", texts)    # one line, both names
        self.assertTrue(all(len(r.split(",")) == 12 for r in rows))
        with tempfile.TemporaryDirectory() as ex:
            self.assertTrue(draw.write_levels(ex, {"EURUSD": lv}, {"EURUSD": EURUSD}, now, {}))
            self.assertFalse(draw.write_levels(ex, {"EURUSD": lv}, {"EURUSD": EURUSD}, now, {}))   # unchanged


class AlertsTest(unittest.TestCase):
    def test_take_then_close_back_inside_alert_once(self):
        bars = make_bars({(0, 11): (1.1050, 1.0995), (1, 12): (1.1060, 1.0995)})
        now = datetime(2026, 11, 10, 12, 20)
        cfg = {"alerts": DEFAULTS["alerts"], "sessions": SESSIONS}
        sent = {}
        lv = chart_levels(bars, now, SESSIONS)
        first = alerts.check(cfg, "EURUSD", lv, bars, EURUSD, now, 0.0, sent)
        msgs = " | ".join(m for _, m in first)
        self.assertIn("took PDH 1.10500", msgs)
        self.assertIn("closed back below it (swept", msgs)       # the 12:00 M15 closed at 1.1000
        self.assertEqual(alerts.check(cfg, "EURUSD", lv, bars, EURUSD, now, 0.0, sent), [])   # once only

    def test_old_takes_never_alert(self):
        bars = make_bars({(0, 11): (1.1050, 1.0995), (1, 4): (1.1060, 1.0995)})
        now = datetime(2026, 11, 10, 12, 0)                     # taken at 04:00, long before now
        cfg = {"alerts": DEFAULTS["alerts"], "sessions": SESSIONS}
        lv = chart_levels(bars, now, SESSIONS)
        self.assertEqual(alerts.check(cfg, "EURUSD", lv, bars, EURUSD, now, 0.0, {}), [])


RULE = '''
NAME = "test"
TIMEFRAME = "M15"
def check(ctx):
    seen = max(b.h for b in ctx.bars("M5"))
    ctx.memory["max"] = max(ctx.memory.get("max", 0), seen)
    if ctx.last("M15").h > 1.1040:
        return f"spike {ctx.fmt(ctx.last('M15').h)}"
'''


class RulesTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, "spike.py")
        with open(self.path, "w") as f:
            f.write(RULE)

    def test_context_never_sees_the_future(self):
        bars = make_bars({(1, 14): (1.1100, 1.0995)})
        rule = rules.load_rule(self.path)
        mem = {}
        ctx = rules.Context("EURUSD", datetime(2026, 11, 10, 14, 0), bars, EURUSD, {"sessions": SESSIONS}, 0, mem)
        self.assertIsNone(rule.module.check(ctx))
        self.assertEqual(mem["max"], 1.1005)
        self.assertEqual(closed(bars["M15"], "M15", datetime(2026, 11, 10, 14, 0))[-1].t, datetime(2026, 11, 10, 13, 45))

    def test_replay_finds_the_spike(self):
        bars = make_bars({(1, 14): (1.1100, 1.0995)})
        with tempfile.TemporaryDirectory() as ex:
            for tf, series in bars.items():
                with open(os.path.join(ex, f"EURUSD_{tf}.csv"), "w") as f:
                    f.write("time,open,high,low,close,tick_volume,spread\n")
                    f.writelines(f"{b.t:%Y.%m.%d %H:%M},{b.o},{b.h},{b.l},{b.c},0,0\n" for b in series)
            with open(os.path.join(ex, "quotes.csv"), "w") as f:
                f.write("symbol,bid,ask,spread_points,digits,point\nEURUSD,1.10000,1.10002,2,5,0.00001\n")
            hits = rules.replay({"export_dir": ex, "symbols": ["EURUSD"], "sessions": SESSIONS}, self.path, days=3)
        # The 14:00-15:00 spike: one hit per M15 candle, each at its close; nothing before 14:15.
        self.assertEqual([(t.strftime("%d %H:%M"), m) for _, t, m in hits],
                         [("10 14:15", "spike 1.11000"), ("10 14:30", "spike 1.11000"),
                          ("10 14:45", "spike 1.11000"), ("10 15:00", "spike 1.11000")])

    def test_live_run_skips_first_sight_then_fires_once(self):
        bars = make_bars({(1, 14): (1.1100, 1.0995)})
        state = {}
        sent = []
        orig = rules.notify.send
        rules.notify.send = lambda cfg, text, kind="": sent.append(text)
        orig_files, orig_log = rules.rule_files, rules.log
        rules.rule_files = lambda folder=None: [self.path]
        rules.log = lambda msg: None                   # keep the repo's data/engine.log clean
        try:
            cfg = {"sessions": SESSIONS}
            # Started at 14:30, mid-spike: that first look must not fire (no back-firing on start); 14:35 is the same
            # candle; 14:45 is a new spike candle and fires once.
            for minute in (30, 35, 45):
                rules.run_live(cfg, "EURUSD", bars, EURUSD, datetime(2026, 11, 10, 14, minute), 0, [], state)
        finally:
            rules.notify.send = orig
            rules.rule_files, rules.log = orig_files, orig_log
        self.assertEqual(sent, ["EURUSD · test: spike 1.11000"])


def deal(n, pos, t, typ, entry, vol, price, sl="0.00000", profit="0.00", comm="-1.00", reason="client"):
    return {"deal": str(n), "position": str(pos), "time": t, "symbol": "EURUSD", "type": typ, "entry": entry,
            "volume": str(vol), "price": str(price), "sl": sl, "tp": "0.00000", "profit": profit,
            "commission": comm, "swap": "0.00", "fee": "0.00", "reason": reason, "comment": ""}


class JournalTest(unittest.TestCase):
    def test_r_uses_the_initial_stop_and_open_positions_are_skipped(self):
        deals = [deal(1, 10, "2026.11.10 10:00:00", "buy", "in", 0.5, 1.1000, sl="1.09900"),
                 deal(2, 10, "2026.11.10 11:00:00", "sell", "out", 0.5, 1.1020, sl="1.10100", profit="100.00",
                      comm="-1.00", reason="tp"),
                 deal(3, 11, "2026.11.10 12:00:00", "sell", "in", 0.2, 1.1010),                 # stop added later
                 deal(4, 11, "2026.11.10 12:30:00", "buy", "out", 0.2, 1.1030, profit="-40.00", reason="sl"),
                 deal(5, 12, "2026.11.10 13:00:00", "buy", "in", 1.0, 1.1000),                  # still open
                 deal(6, 12, "2026.11.10 13:10:00", "sell", "out", 0.4, 1.1010, profit="40.00"),
                 {"deal": "7", "position": "0", "time": "2026.11.09 00:00:00", "symbol": "", "type": "balance",
                  "entry": "in", "volume": "0", "price": "0", "sl": "0", "tp": "0", "profit": "5000", "commission": "0",
                  "swap": "0", "fee": "0", "reason": "client", "comment": ""}]
        seen = {"Demo_1234:11": {"sl": "1.10300"}}
        trades = {t["id"]: t for t in journal.build_trades(deals, "Demo_1234", 0.0, {"EURUSD": EURUSD}, seen)}
        self.assertEqual(sorted(trades), ["Demo_1234:10", "Demo_1234:11"])
        a, b = trades["Demo_1234:10"], trades["Demo_1234:11"]
        # Net includes commission on both deals; risk = 10 pips x 0.5 lots at $1 per point-lot.
        self.assertEqual((a["risk"], a["r"], a["net"], a["exit_reason"]), ("50.00", "+1.96", "98.00", "tp"))
        self.assertEqual((b["sl"], b["risk"], b["r"]), ("1.10300", "40.00", "-1.05"))   # first stop seen on the position


class NotifyTest(unittest.TestCase):
    def test_queue_ids_and_tags(self):
        with tempfile.TemporaryDirectory() as ex:
            cfg = {"export_dir": ex, "push": {"mt5": True, "telegram": False}}
            notify.send(cfg, "one", "level")
            notify.send(cfg, "two\twith tab", "")
            with open(os.path.join(ex, "notify.tsv"), encoding="utf-8") as f:
                rows = [line.rstrip("\n").split("\t") for line in f]
        self.assertEqual(rows[0], ["id", "time", "text"])
        self.assertEqual([r[0] for r in rows[1:]], ["1", "2"])
        self.assertEqual(rows[1][2], "💧 LEVEL one")
        self.assertEqual(rows[2][2], "two with tab")


class FreshCloneTest(unittest.TestCase):
    def test_replace_waits_out_a_reader(self):
        from traderclaw import store
        calls = []
        real = store.os.replace

        def busy_twice(a, b):                     # Windows: the target is open in MT5 for a moment
            calls.append(1)
            if len(calls) < 3:
                raise PermissionError("in use")
            real(a, b)
        with tempfile.TemporaryDirectory() as d:
            src, dst = os.path.join(d, "a.tmp"), os.path.join(d, "a")
            with open(src, "w") as f:
                f.write("x")
            store.os.replace = busy_twice
            try:
                store.replace(src, dst)
            finally:
                store.os.replace = real
            self.assertEqual((len(calls), os.path.exists(dst)), (3, True))

    def test_lock_creates_its_folder(self):
        from traderclaw.store import locked
        with tempfile.TemporaryDirectory() as d:
            with locked(os.path.join(d, "journal", "trades.csv")):      # journal/ isn't in git, so it may not exist
                self.assertTrue(os.path.isdir(os.path.join(d, "journal")))


class ConfigTest(unittest.TestCase):
    def test_bad_session_and_missing_export(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "config.json")
            for bad in ({"export_dir": d, "sessions": [{"name": "X", "from": 22, "to": 3}]},
                        {"export_dir": "<MT5 data folder>/MQL5/Files/traderclaw"}):
                with open(p, "w") as f:
                    json.dump(bad, f)
                with self.assertRaises(ConfigError):
                    load(p)


class ReadOnlyTest(unittest.TestCase):
    """The kit must never be able to trade. This fails if anyone (or any agent) adds trading calls."""

    def test_no_trading_calls_anywhere(self):
        mql = re.compile(r"\b(OrderSend|OrderSendAsync|CTrade|PositionClose|PositionModify|OrderModify|OrderDelete|"
                         r"MqlTradeRequest|TRADE_ACTION_\w+)\b")
        py = re.compile(r"\b(order_send|order_check|MetaTrader5|import\s+mt5)\b")
        files = glob.glob(os.path.join(ROOT, "mt5", "**", "*.mq*"), recursive=True)
        files += glob.glob(os.path.join(ROOT, "traderclaw", "*.py")) + glob.glob(os.path.join(ROOT, "rules", "*.py"))
        self.assertTrue(files)
        for path in files:
            with open(path, encoding="utf-8", errors="replace") as f:
                text = f.read()
            pat = mql if path.endswith((".mq5", ".mqh")) else py
            self.assertIsNone(pat.search(text), f"trading call in {os.path.relpath(path, ROOT)}")


if __name__ == "__main__":
    unittest.main()
