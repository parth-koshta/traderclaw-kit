"""Reading the MT5 export (the TraderClaw service writes it) and basic series maths.

Times in the export are MT5 server time, kept here as naive datetimes. A bar's time is its open; it has closed once
open + timeframe <= now. Messages to you are shown in your computer's local time (local_time).
"""
from __future__ import annotations

import bisect
import csv
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

TF_MINUTES = {"M1": 1, "M5": 5, "M15": 15, "H1": 60, "H4": 240, "D1": 1440}
TIME_FMT = "%Y.%m.%d %H:%M"


@dataclass
class Bar:
    t: datetime
    o: float
    h: float
    l: float
    c: float
    v: float = 0.0     # tick volume (forex has no central volume)
    spread: int = 0    # points

    def end(self, tf: str) -> datetime:
        return self.t + timedelta(minutes=TF_MINUTES[tf])


def parse_time(s: str) -> datetime:
    s = s.strip()
    if len(s) >= 19:
        return datetime.strptime(s[:19], "%Y.%m.%d %H:%M:%S")
    if len(s) >= 16:
        return datetime.strptime(s[:16], TIME_FMT)
    return datetime.strptime(s, "%Y.%m.%d")


def fmt_time(t: datetime) -> str:
    return t.strftime(TIME_FMT)


def read_kv(path: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    if not os.path.exists(path):
        return out
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            if "=" in line:
                k, v = line.rstrip("\r\n").split("=", 1)
                out[k.strip()] = v.strip()
    return out


def read_csv(path: str) -> List[dict]:
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8", errors="replace") as f:
        return list(csv.DictReader(f))


def load_bars(export_dir: str, symbol: str, tf: str) -> List[Bar]:
    bars = []
    for r in read_csv(os.path.join(export_dir, f"{symbol}_{tf}.csv")):
        bars.append(Bar(parse_time(r["time"]), float(r["open"]), float(r["high"]), float(r["low"]), float(r["close"]),
                        float(r.get("tick_volume") or 0), int(r.get("spread") or 0)))
    return bars


def load_all(export_dir: str, symbol: str) -> Dict[str, List[Bar]]:
    return {tf: load_bars(export_dir, symbol, tf) for tf in TF_MINUTES}


def closed(bars: List[Bar], tf: str, now: datetime) -> List[Bar]:
    """The bars that have fully closed by `now` (oldest first)."""
    cutoff = now - timedelta(minutes=TF_MINUTES[tf])          # closed  <=>  t <= now - tf
    if not bars or bars[-1].t <= cutoff:
        return bars
    return bars[:bisect.bisect_right([b.t for b in bars], cutoff)]


def upto(bars: List[Bar], now: datetime) -> List[Bar]:
    """Every bar that opened before `now`, the forming one too (a bar opening exactly at `now` has no prices yet)."""
    if not bars or bars[-1].t < now:
        return bars
    return bars[:bisect.bisect_left([b.t for b in bars], now)]


def atr(bars: List[Bar], n: int = 14) -> float:
    if len(bars) < 2:
        return 0.0
    trs = [max(b.h - b.l, abs(b.h - p.c), abs(b.l - p.c)) for p, b in zip(bars, bars[1:])]
    trs = trs[-n:]
    return sum(trs) / len(trs)


def swings(bars: List[Bar], n: int, kind: str) -> List[int]:
    """Indexes of swing highs (or lows): a bar higher (lower) than the n bars on each side."""
    out = []
    for i in range(n, len(bars) - n):
        x = bars[i].h if kind == "high" else bars[i].l
        side = bars[i - n:i] + bars[i + 1:i + n + 1]
        if kind == "high" and all(x > b.h for b in side) or kind == "low" and all(x < b.l for b in side):
            out.append(i)
    return out


@dataclass
class Status:
    server_time: Optional[datetime]
    gmt_time: Optional[datetime]
    offset_hours: float
    account_key: str
    company: str
    symbols: List[str]
    errors: str
    version: str

    def age_seconds(self) -> float:
        """How old the export is."""
        if not self.gmt_time:
            return float("inf")
        return (datetime.now(timezone.utc).replace(tzinfo=None) - self.gmt_time).total_seconds()


def read_status(export_dir: str) -> Optional[Status]:
    kv = read_kv(os.path.join(export_dir, "status.txt"))
    if not kv:
        return None
    t = kv.get("exported_server_time")
    g = kv.get("exported_gmt_time")
    return Status(parse_time(t) if t else None, parse_time(g) if g else None,
                  float(kv.get("server_gmt_offset_hours") or 0), kv.get("account_key", ""), kv.get("account_company", ""),
                  [s for s in kv.get("symbols", "").split(",") if s], kv.get("errors", ""), kv.get("service_version", ""))


def local_time(server: datetime, offset_hours: float) -> datetime:
    """Server time -> your computer's local time (naive)."""
    utc = (server - timedelta(hours=offset_hours)).replace(tzinfo=timezone.utc)
    return utc.astimezone().replace(tzinfo=None)


@dataclass
class SymbolInfo:
    symbol: str
    digits: int
    point: float
    bid: float
    ask: float
    tick_value: float = 0.0   # account currency per tick per lot (MT5's value, at the current price)
    tick_size: float = 0.0

    @property
    def pip(self) -> float:
        """A pip: 10 points on 3- and 5-digit prices (forex), else one point."""
        return self.point * 10 if self.digits in (3, 5) else self.point

    def fmt(self, price: float) -> str:
        return f"{price:.{self.digits}f}"

    def money(self, distance: float, lots: float) -> float:
        """Account-currency value of a price distance on `lots`, from MT5's tick value. Without one (older export),
        a USD estimate for USD-quoted symbols (EURUSD, XAUUSD, USDJPY...); 0 when unknown."""
        if self.tick_size > 0 and self.tick_value > 0:
            return abs(distance) / self.tick_size * self.tick_value * lots
        s = self.symbol.upper()
        contract = 100.0 if s.startswith("XAU") else 5000.0 if s.startswith("XAG") else 100000.0
        if s[3:6] == "USD":
            return abs(distance) * contract * lots
        if s.startswith("USD") and self.bid > 0:
            return abs(distance) * contract * lots / self.bid
        return 0.0


def read_quotes(export_dir: str) -> Dict[str, SymbolInfo]:
    out = {}
    for r in read_csv(os.path.join(export_dir, "quotes.csv")):
        try:
            out[r["symbol"]] = SymbolInfo(r["symbol"], int(r["digits"]), float(r["point"]), float(r["bid"]),
                                          float(r["ask"]), float(r.get("tick_value") or 0), float(r.get("tick_size") or 0))
        except (KeyError, ValueError):
            continue
    return out


def guess_info(symbol: str, bars: List[Bar]) -> SymbolInfo:
    """When quotes.csv has no row for the symbol (tests, replays): digits from the prices."""
    digits = 2
    for b in bars[-200:]:
        for x in (b.o, b.h, b.l, b.c):
            s = f"{x:.6f}".rstrip("0")
            digits = max(digits, len(s.split(".")[1]) if "." in s else 0)
    digits = min(digits, 5)
    last = bars[-1].c if bars else 0.0
    return SymbolInfo(symbol, digits, 10 ** -digits, last, last)
