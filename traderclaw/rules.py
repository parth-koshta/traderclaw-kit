"""Your custom alert rules: one Python file per rule in rules/, written by you or your AI agent (see rules/README.md).

    NAME = "London sweep of the Tokyo low"     # shown in the push
    ENABLED = True                             # False = kept but not run
    SYMBOLS = ["EURUSD", "GBPUSD"]             # None = every symbol in config.json
    TIMEFRAME = "M5"                           # check() runs once per closed candle of this timeframe

    def check(ctx):
        ...                                    # return a message (str), a list of messages, or None

The engine calls check() right after each candle of TIMEFRAME closes, with a Context as of that close. A message is
pushed once per rule, symbol and candle. Replay a rule over the exported history before switching it on:

    python3 -m traderclaw replay rules/my_rule.py --days 3
"""
from __future__ import annotations

import glob
import importlib.util
import os
import traceback
from dataclasses import dataclass
from datetime import datetime, timedelta
from types import ModuleType
from typing import Any, Dict, List, Optional, Tuple

from . import notify
from .config import RULES
from .data import (TF_MINUTES, Bar, SymbolInfo, atr, closed, fmt_time, guess_info, load_all, local_time, read_quotes,
                   swings)
from .levels import Level, chart_levels, find
from .store import log


class Context:
    """What a rule sees: everything as of `now`, the close of the candle being checked (server time). Nothing after
    `now` is visible, in replays too."""

    def __init__(self, symbol: str, now: datetime, bars: Dict[str, List[Bar]], info: SymbolInfo, cfg: dict,
                 offset_hours: float, memory: dict, positions: Optional[List[dict]] = None, live: bool = True):
        self.symbol, self.now, self.info, self.cfg = symbol, now, info, cfg
        self.offset_hours = offset_hours
        self.memory = memory              # a dict kept between checks (per rule and symbol); use it for "only once"
        self.positions = positions or []  # your open positions on this symbol (live only; empty in replays)
        self.live = live
        self._all = bars
        self._closed: Dict[str, List[Bar]] = {}
        self._levels: Optional[List[Level]] = None

    # --- candles -----------------------------------------------------------------------------------------------
    def bars(self, tf: str = "M5", n: Optional[int] = None) -> List[Bar]:
        """Closed candles of `tf`, oldest first (b.t open time, b.o, b.h, b.l, b.c, b.v tick volume)."""
        if tf not in self._closed:
            self._closed[tf] = closed(self._all.get(tf, []), tf, self.now)
        out = self._closed[tf]
        return out[-n:] if n else out

    def last(self, tf: str = "M5") -> Optional[Bar]:
        b = self.bars(tf)
        return b[-1] if b else None

    @property
    def price(self) -> float:
        """The latest closed price (M1 if available)."""
        b = self.last("M1") or self.last("M5")
        return b.c if b else 0.0

    def atr(self, tf: str = "M15", n: int = 14) -> float:
        return atr(self.bars(tf)[-(n + 1):], n)

    def swing_highs(self, tf: str = "M15", n: int = 2, lookback: int = 100) -> List[Tuple[datetime, float]]:
        """Swing highs of the last `lookback` candles (higher than the n candles each side), oldest first."""
        b = self.bars(tf)[-lookback:]
        return [(b[i].t, b[i].h) for i in swings(b, n, "high")]

    def swing_lows(self, tf: str = "M15", n: int = 2, lookback: int = 100) -> List[Tuple[datetime, float]]:
        b = self.bars(tf)[-lookback:]
        return [(b[i].t, b[i].l) for i in swings(b, n, "low")]

    # --- levels and sessions --------------------------------------------------------------------------------------
    @property
    def levels(self) -> List[Level]:
        """The chart levels as of now: PWH/PWL, PDH/PDL, yesterday's and today's session highs/lows."""
        if self._levels is None:
            self._levels = chart_levels(self._all, self.now, self.cfg["sessions"], {})
        return self._levels

    def level(self, name: str) -> Optional[Level]:
        """A level by name: "PDH", "PWL", "Tokyo low", "Prev London high", "London high" (running: "(so far)")."""
        return find(self.levels, name)

    def untaken(self, side: Optional[str] = None) -> List[Level]:
        """Untaken finished levels ("high", "low" or both), nearest to the price first."""
        out = [lv for lv in self.levels if not lv.running and lv.is_untaken(self.now) and (side in (None, lv.side))]
        return sorted(out, key=lambda lv: abs(lv.price - self.price))

    def session(self, name: str, days_ago: int = 0) -> Optional[Tuple[float, float]]:
        """(high, low) of a session from config.json, today so far (days_ago=0) or an earlier server day."""
        s = next((x for x in self.cfg["sessions"] if x["name"].lower() == name.lower()), None)
        if not s:
            raise KeyError(f"no session named {name!r} in config.json")
        day = datetime(self.now.year, self.now.month, self.now.day) - timedelta(days=days_ago)
        start, end = day + timedelta(hours=s["from"]), min(day + timedelta(hours=s["to"]), self.now)
        sel = [b for b in self.bars("M5") if start <= b.t < end] or [b for b in self.bars("M15") if start <= b.t < end]
        return (max(b.h for b in sel), min(b.l for b in sel)) if sel else None

    def in_session(self, name: str) -> bool:
        """Is `now` inside that session's hours (server time)?"""
        s = next(x for x in self.cfg["sessions"] if x["name"].lower() == name.lower())
        h = self.now.hour + self.now.minute / 60
        return s["from"] <= h < s["to"]

    # --- time and formatting ---------------------------------------------------------------------------------------
    @property
    def hour(self) -> int:
        return self.now.hour

    @property
    def minute(self) -> int:
        return self.now.minute

    def local(self, t: Optional[datetime] = None) -> str:
        """A server time as HH:MM in your computer's time zone (for messages)."""
        return local_time(t or self.now, self.offset_hours).strftime("%H:%M")

    def fmt(self, price: float) -> str:
        return self.info.fmt(price)


@dataclass
class Rule:
    key: str
    path: str
    module: ModuleType

    @property
    def name(self) -> str:
        return getattr(self.module, "NAME", self.key)

    @property
    def enabled(self) -> bool:
        return bool(getattr(self.module, "ENABLED", True))

    @property
    def symbols(self) -> Optional[List[str]]:
        return getattr(self.module, "SYMBOLS", None)

    @property
    def tf(self) -> str:
        tf = getattr(self.module, "TIMEFRAME", "M5")
        if tf not in TF_MINUTES:
            raise ValueError(f"{self.key}: TIMEFRAME must be one of {', '.join(TF_MINUTES)}")
        return tf


_cache: Dict[str, Tuple[float, Rule]] = {}


def load_rule(path: str) -> Rule:
    """Loads (or reloads, when the file changed) one rule file."""
    path = os.path.abspath(path)
    mtime = os.path.getmtime(path)
    hit = _cache.get(path)
    if hit and hit[0] == mtime:
        return hit[1]
    key = os.path.splitext(os.path.basename(path))[0]
    spec = importlib.util.spec_from_file_location(f"traderclaw_rule_{key}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    if not callable(getattr(module, "check", None)):
        raise ValueError(f"{key}: a rule needs a check(ctx) function")
    rule = Rule(key, path, module)
    _cache[path] = (mtime, rule)
    return rule


def rule_files(folder: str = RULES) -> List[str]:
    return sorted(p for p in glob.glob(os.path.join(folder, "*.py")) if not os.path.basename(p).startswith("_"))


def _messages(res: Any) -> List[str]:
    if not res:
        return []
    items = [res] if isinstance(res, str) else list(res)
    return [" ".join(str(m).split()) for m in items if m]


def run_live(cfg: dict, symbol: str, bars: Dict[str, List[Bar]], info: SymbolInfo, now: datetime, offset: float,
             positions: List[dict], state: dict) -> None:
    """Runs every enabled rule for this symbol on its newest closed candle, once."""
    seen = state.setdefault("rules", {})
    memory = state.setdefault("rule_memory", {})
    errors = state.setdefault("rule_errors", {})
    for path in rule_files():
        key = os.path.splitext(os.path.basename(path))[0]
        try:
            rule = load_rule(path)
            if not rule.enabled or (rule.symbols and symbol not in rule.symbols):
                continue
            last = closed(bars.get(rule.tf, []), rule.tf, now)
            if not last:
                continue
            close = last[-1].end(rule.tf)
            k = f"{key}:{symbol}"
            prev = seen.get(k)
            seen[k] = fmt_time(close)
            if prev is None or prev >= fmt_time(close):
                continue                        # first sight (no back-firing on start) or already checked
            ctx = Context(symbol, close, bars, info, cfg, offset, memory.setdefault(k, {}), positions)
            for msg in _messages(rule.module.check(ctx)):
                notify.send(cfg, f"{symbol} · {rule.name}: {msg}", "alert")
                log(f"rule {key} {symbol}: {msg}")
        except Exception as e:
            day = now.strftime("%Y-%m-%d")
            log(f"rule {key} failed on {symbol}: {traceback.format_exc(limit=3)}")
            if errors.get(key) != day:
                errors[key] = day
                notify.send(cfg, f"Rule {key} failed ({type(e).__name__}: {str(e)[:80]}). It keeps being tried; "
                                 f"ask your agent to fix it.", "system")


def replay(cfg: dict, path: str, days: float = 3, symbols: Optional[List[str]] = None,
           offset: float = 0.0) -> List[Tuple[str, datetime, str]]:
    """Every message the rule would have sent over the last `days` of the exported candles, as (symbol, server close
    time, message). Ignores ENABLED. Limited by what MT5 exports: M1 ~1 day, M5 ~4 days, M15 ~10 days, H1 ~1 month."""
    rule = load_rule(path)
    quotes = read_quotes(cfg["export_dir"])
    out = []
    for sym in symbols or rule.symbols or cfg["symbols"]:
        bars = load_all(cfg["export_dir"], sym)
        series = bars.get(rule.tf, [])
        if not series:
            continue
        info = quotes.get(sym) or guess_info(sym, bars.get("M5") or series)
        end = series[-1].t                      # the last bar may still be forming
        start = end - timedelta(days=days)
        memory: dict = {}
        for b in series:
            close = b.end(rule.tf)
            if b.t < start or close > end:
                continue
            ctx = Context(sym, close, bars, info, cfg, offset, memory, live=False)
            for msg in _messages(rule.module.check(ctx)):
                out.append((sym, close, msg))
    return out
