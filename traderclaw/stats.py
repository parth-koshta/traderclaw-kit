"""Journal statistics from journal/trades.csv.

    python3 -m traderclaw stats [--days 30] [--account KEY]
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from .data import parse_time


def _block(rows: List[dict]) -> Dict[str, str]:
    rs = [float(r["r"]) for r in rows if r.get("r")]
    net = sum(float(r["net"]) for r in rows)
    wins = [x for x in rs if x > 0]
    losses = [x for x in rs if x <= 0]
    return {
        "trades": str(len(rows)),
        "with R": str(len(rs)),
        "win rate": f"{len(wins) / len(rs):.0%}" if rs else "-",
        "avg win": f"{sum(wins) / len(wins):+.2f}R" if wins else "-",
        "avg loss": f"{sum(losses) / len(losses):+.2f}R" if losses else "-",
        "expectancy": f"{sum(rs) / len(rs):+.2f}R" if rs else "-",
        "net": f"{net:+.2f}",
    }


def session_of(server_time: str, sessions: List[dict]) -> str:
    t = parse_time(server_time)
    h = t.hour + t.minute / 60
    return next((s["name"] for s in sessions if s["from"] <= h < s["to"]), "other")


def report(rows: List[dict], cfg: dict, days: Optional[int] = None, account: Optional[str] = None) -> str:
    if days:
        cutoff = datetime.now() - timedelta(days=days)
        rows = [r for r in rows if datetime.strptime(r["close_local"], "%Y-%m-%d %H:%M") >= cutoff]
    if account:
        rows = [r for r in rows if r["account"] == account]
    if not rows:
        return "No closed trades in that range."
    lines = []
    cols = list(_block(rows))

    def table(title: str, groups: Dict[str, List[dict]]) -> None:
        lines.append(f"\n{title}")
        lines.append(f"{'':16}" + "".join(f"{c:>11}" for c in cols))
        for k in sorted(groups, key=lambda k: -len(groups[k])):
            b = _block(groups[k])
            lines.append(f"{k[:16]:16}" + "".join(f"{b[c]:>11}" for c in cols))

    table("All trades (R from the initial stop; trades without a stop count in net only)", {"all": rows})
    for title, key in (("By symbol", lambda r: r["symbol"]),
                       ("By session (opened in)", lambda r: session_of(r["open_server"], cfg["sessions"])),
                       ("By setup", lambda r: r.get("setup") or "(not tagged)"),
                       ("By execution grade", lambda r: r.get("grade") or "(not reviewed)"),
                       ("By weekday", lambda r: datetime.strptime(r["open_local"], "%Y-%m-%d %H:%M").strftime("%a"))):
        groups: Dict[str, List[dict]] = defaultdict(list)
        for r in rows:
            groups[key(r)].append(r)
        table(title, groups)
    lines.append("\nSmall samples mislead: under ~30 trades in a group, treat it as a hint, not evidence.")
    return "\n".join(lines)
