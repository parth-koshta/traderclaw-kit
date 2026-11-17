"""The levels drawn on your charts and used by the built-in alerts:

- last week's high/low (PWH/PWL; a week runs from server Monday 00:00 to Friday 24:00, like MT5's W1 candle)
- the previous day's high/low (PDH/PDL; a day is the broker's D1 candle)
- the previous day's session highs/lows ("Prev London high")
- today's session highs/lows: finished ones, and the running one labelled "(so far)"

Each is marked taken at the first trade beyond it after it formed.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from .data import Bar, closed, upto


@dataclass
class Level:
    side: str                 # "high" or "low"
    price: float
    formed: datetime          # when the level exists (session end, week start, ...)
    source: datetime          # time of the candle that made the extreme (where its line starts)
    family: str               # PW, PD, Session (today) or PrevSession (yesterday's sessions)
    label: str                # "PDL", "London high (so far)", "Prev NY low"
    taken_at: Optional[datetime] = None

    @property
    def name(self) -> str:
        return self.label.replace(" (so far)", "")

    @property
    def running(self) -> bool:
        return self.label.endswith("(so far)")

    def beyond(self, price: float) -> bool:
        return price > self.price if self.side == "high" else price < self.price

    def is_untaken(self, at: datetime) -> bool:
        return self.taken_at is None or self.taken_at > at


def _sessions(m15: List[Bar], m5: Optional[List[Bar]], day: datetime, now: datetime, sessions: List[dict],
              prefix: str, family: str) -> List[Level]:
    """Finished sessions' highs and lows of `day`. With m5 (the forming bar included), the running session's too,
    labelled "(so far)" and formed now, so it's never taken."""
    out = []
    for s in sessions:
        start, end = day + timedelta(hours=s["from"]), day + timedelta(hours=s["to"])
        running = end > now
        if running and (m5 is None or now < start):
            continue
        sel = [x for x in (m5 if running else m15) if start <= x.t < end]
        if not sel:
            continue
        hi, lo = max(sel, key=lambda x: x.h), min(sel, key=lambda x: x.l)
        formed, tail = (now, " (so far)") if running else (end, "")
        out.append(Level("high", hi.h, formed, hi.t, family, f"{prefix}{s['name']} high{tail}"))
        out.append(Level("low", lo.l, formed, lo.t, family, f"{prefix}{s['name']} low{tail}"))
    return out


def chart_levels(bars: Dict[str, List[Bar]], now: datetime, sessions: List[dict],
                 opts: Optional[dict] = None) -> List[Level]:
    """bars: timeframe -> bars (the forming one may be included; anything after `now` is ignored)."""
    opts = opts or {}
    m5 = upto(bars.get("M5", []), now)
    m15 = closed(bars.get("M15", []), "M15", now)
    h1 = closed(bars.get("H1", []), "H1", now)
    d1 = closed(bars.get("D1", []), "D1", now)
    today = datetime(now.year, now.month, now.day)
    week = today - timedelta(days=today.weekday())
    out: List[Level] = []

    days = [d for d in d1 if week - timedelta(days=7) <= d.t < week]
    if days and opts.get("previous_week", True):
        hours = [x for x in h1 if week - timedelta(days=7) <= x.t < week] or days
        out.append(Level("high", max(d.h for d in days), week, max(hours, key=lambda x: x.h).t, "PW", "PWH"))
        out.append(Level("low", min(d.l for d in days), week, min(hours, key=lambda x: x.l).t, "PW", "PWL"))

    prev = [d for d in d1 if d.t < today]
    if prev:
        y = prev[-1]
        if opts.get("previous_day", True):
            day_m15 = [x for x in m15 if y.t <= x.t < today]
            hi = max(day_m15, key=lambda x: x.h).t if day_m15 else y.t
            lo = min(day_m15, key=lambda x: x.l).t if day_m15 else y.t
            out += [Level("high", y.h, today, hi, "PD", "PDH"), Level("low", y.l, today, lo, "PD", "PDL")]
        if opts.get("previous_day_sessions", True):
            out += _sessions(m15, None, y.t, now, sessions, "Prev ", "PrevSession")
    if opts.get("today_sessions", True):
        out += _sessions(m15, m5, today, now, sessions, "", "Session")

    for lv in out:
        mark_taken(lv, d1, h1, m5)
    return out


def mark_taken(lv: Level, d1: List[Bar], h1: List[Bar], m5: List[Bar]) -> None:
    """First trade beyond the level after it formed. M5 covers only a few days, so older stretches are checked on H1
    and then D1 (coarser time, same answer for taken or not)."""
    lv.taken_at = None
    if lv.running:
        return
    start_m5 = m5[0].t if m5 else None
    start_h1 = h1[0].t if h1 else start_m5
    for series, until, minutes in ((d1, start_h1, 1440), (h1, start_m5, 60), (m5, None, 5)):
        for b in series:
            if b.t + timedelta(minutes=minutes) <= lv.formed or (until is not None and b.t >= until):
                continue
            if b.h > lv.price if lv.side == "high" else b.l < lv.price:
                lv.taken_at = max(b.t, lv.formed)
                return


def find(levels: List[Level], name: str) -> Optional[Level]:
    """A level by name, e.g. "PDL", "London low", "Prev NY high" ("(so far)" is optional)."""
    key = name.replace(" (so far)", "").strip().lower()
    return next((lv for lv in levels if lv.name.lower() == key), None)
