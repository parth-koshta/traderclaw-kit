"""Built-in alerts (config.json "alerts"), all about the chart levels:

- level_taken: a level traded through for the first time ("EURUSD took PDL 1.10850 at 14:32")
- close_after_take: the first M15 close after that, back inside (swept) or beyond (accepted)
- session_open: at each session's open, the nearest untaken levels above and below

Each alert is sent once. Only events from the last 30 minutes alert, so starting the engine never replays old ones.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, List, Tuple

from .data import Bar, SymbolInfo, closed, fmt_time, local_time
from .levels import Level

RECENT = timedelta(minutes=30)


def check(cfg: dict, symbol: str, levels: List[Level], bars: Dict[str, List[Bar]], info: SymbolInfo, now: datetime,
          offset: float, sent: Dict[str, str]) -> List[Tuple[str, str]]:
    """New (kind, message) pairs; `sent` (key -> server time) remembers what went out."""
    a = cfg.get("alerts", {})
    fams = set(a.get("families", ["PW", "PD", "Session"]))
    out: List[Tuple[str, str]] = []
    hm = lambda t: local_time(t, offset).strftime("%H:%M")   # noqa: E731

    def once(key: str, kind: str, msg: str) -> None:
        if key not in sent:
            sent[key] = fmt_time(now)
            out.append((kind, msg))

    m15 = closed(bars.get("M15", []), "M15", now)
    for lv in levels:
        if lv.family not in fams or lv.taken_at is None:
            continue
        ident = f"{symbol}:{lv.name}:{info.fmt(lv.price)}:{lv.formed:%Y%m%d%H}"
        if a.get("level_taken", True) and lv.taken_at >= now - RECENT:
            once(f"take:{ident}", "level", f"{symbol} took {lv.name} {info.fmt(lv.price)} at {hm(lv.taken_at)}")
        if a.get("close_after_take", True):
            b = next((x for x in m15 if x.end("M15") > lv.taken_at), None)
            if b and b.end("M15") >= now - RECENT:
                if lv.beyond(b.c):
                    how = f"closed {'above' if lv.side == 'high' else 'below'} it (accepted)"
                else:
                    how = f"closed back {'below' if lv.side == 'high' else 'above'} it (swept, not accepted)"
                once(f"close:{ident}", "level",
                     f"{symbol} {lv.name} {info.fmt(lv.price)}: the {hm(b.t)} M15 candle {how} at {info.fmt(b.c)}")

    if a.get("session_open"):
        today = datetime(now.year, now.month, now.day)
        for s in cfg["sessions"]:
            start = today + timedelta(hours=s["from"])
            if start <= now < start + RECENT:
                ready = [lv for lv in levels if not lv.running and lv.is_untaken(now)]
                price = bars["M5"][-1].c if bars.get("M5") else 0.0
                above = sorted((lv for lv in ready if lv.price > price), key=lambda lv: lv.price)[:2]
                below = sorted((lv for lv in ready if lv.price < price), key=lambda lv: -lv.price)[:2]
                txt = lambda ls: ", ".join(f"{lv.name} {info.fmt(lv.price)}" for lv in ls) or "none"   # noqa: E731
                once(f"open:{symbol}:{start:%Y%m%d%H}", "session",
                     f"{s['name']} open · {symbol} {info.fmt(price)} · untaken above: {txt(above)} · below: {txt(below)}")
    return out


def prune(sent: Dict[str, str], now: datetime, days: int = 4) -> None:
    cutoff = fmt_time(now - timedelta(days=days))
    for k in [k for k, v in sent.items() if v < cutoff]:
        del sent[k]
