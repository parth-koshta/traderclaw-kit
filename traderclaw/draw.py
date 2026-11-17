"""draw_levels.csv for the MT5 service: one labelled line per level. Amber from the candle that made it to the right
edge while untaken (dashed for the running session); grey dotted to the candle that took it once taken. Levels at the
same price and status share one line, their names joined: "PWL · PDL · Prev NY low 1.11310".

File format (every draw*.csv the service reads):
    version,<n>                      the service redraws a chart only when this changes
    symbol,type,name,time1,price1,time2,price2,color,style,width,timeframes,text
type: hline | trend | rect | vline | text | arrow_up | arrow_down · color #RRGGBB · style solid | dash | dot ·
timeframes "all" or e.g. M1|M5|M15 · times are server time YYYY.MM.DD HH:MM · no commas in the text.
"""
from __future__ import annotations

import hashlib
import os
from datetime import datetime, timedelta
from typing import Dict, List

from .data import SymbolInfo, fmt_time
from .levels import Level
from .store import replace

HEADER = "symbol,type,name,time1,price1,time2,price2,color,style,width,timeframes,text"
UNTAKEN, TAKEN = "#d97706", "#6b7280"
# Sessions show up to H1 (an H4 candle spans two sessions); the day and week up to D1.
TFS = {"Session": "M1|M5|M15|M30|H1", "PrevSession": "M1|M5|M15|M30|H1",
       "PD": "M1|M5|M15|M30|H1|H4|D1", "PW": "M1|M5|M15|M30|H1|H4|D1"}
ORDER = ("PW", "PD", "Session", "PrevSession")


def write_file(export_dir: str, name: str, rows: List[str]) -> bool:
    """Atomic write with a content-hash version; returns False when nothing changed."""
    body = "\n".join(rows)
    version = int(hashlib.md5(body.encode()).hexdigest()[:7], 16)
    path = os.path.join(export_dir, name)
    try:
        with open(path, encoding="utf-8") as f:
            if f.readline().strip() == f"version,{version}":
                return False
    except OSError:
        pass
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(f"version,{version}\n{HEADER}\n{body}\n")
    replace(tmp, path)
    return True


def right_edge(now: datetime) -> datetime:
    """Untaken lines run to 2 hours past the current hour, so the file changes hourly, not every minute."""
    return datetime(now.year, now.month, now.day, now.hour) + timedelta(hours=2)


def level_rows(levels: Dict[str, List[Level]], infos: Dict[str, SymbolInfo], now: datetime,
               same: Dict[str, float]) -> List[str]:
    rows: List[str] = []
    for sym, lvs in levels.items():
        info = infos[sym]
        tol = max(same.get(sym, 0.0), info.point / 2)
        for taken in (False, True):
            groups: List[List[Level]] = []
            for lv in sorted((x for x in lvs if x.is_untaken(now) != taken), key=lambda x: -x.price):
                if groups and groups[-1][0].price - lv.price <= tol:
                    groups[-1].append(lv)
                else:
                    groups.append([lv])
            for g in groups:
                g.sort(key=lambda x: ORDER.index(x.family))
                names = " · ".join(dict.fromkeys(x.name for x in g))
                so_far = any(x.running for x in g)
                text = f"{names} {info.fmt(g[0].price)}" + (" (so far)" if so_far else "") + (" taken" if taken else "")
                end = fmt_time(g[0].taken_at if taken and g[0].taken_at else right_edge(now))
                style = "dot" if taken else ("dash" if all(x.running for x in g) else "solid")
                tfs = max((TFS[x.family] for x in g), key=len)
                price = info.fmt(g[0].price)
                rows.append(f"{sym},trend,lv{len(rows)},{fmt_time(min(x.source for x in g))},{price},{end},{price},"
                            f"{TAKEN if taken else UNTAKEN},{style},1,{tfs},{text}")
    return rows


def write_levels(export_dir: str, levels: Dict[str, List[Level]], infos: Dict[str, SymbolInfo], now: datetime,
                 same: Dict[str, float]) -> bool:
    return write_file(export_dir, "draw_levels.csv", level_rows(levels, infos, now, same))
