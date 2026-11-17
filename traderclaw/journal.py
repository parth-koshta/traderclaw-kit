"""The trade journal, built from MT5's own deal history, so every trade is in it without typing anything.

- journal/trades.csv  one row per closed trade (facts from MT5, plus setup/grade/note that the review or you add)
- journal/journal.md  the same as a readable table (regenerated; edit through `journal tag`, not by hand)
- journal/reviews.md  the AI reviews and your own notes, newest at the bottom

R uses the initial stop: the stop on the opening deal, or the first stop the engine saw on the open position (set the
stop within a minute of opening and it's caught). Risk in money comes from MT5's tick value for the symbol.

    python3 -m traderclaw journal                         # update and show the latest trades
    python3 -m traderclaw journal tag <id> setup="London sweep" grade=B note="moved stop early"
"""
from __future__ import annotations

import csv
import glob
import os
import re
from datetime import datetime
from typing import Dict, List, Optional

from .config import DATA, JOURNAL
from .data import local_time, parse_time, read_csv, read_quotes
from .store import load_json, locked, log, replace, save_json

TRADES = os.path.join(JOURNAL, "trades.csv")
TABLE = os.path.join(JOURNAL, "journal.md")
REVIEWS = os.path.join(JOURNAL, "reviews.md")
SEEN = os.path.join(DATA, "seen_positions.json")
FIELDS = ["id", "account", "symbol", "side", "lots", "open_server", "close_server", "open_local", "close_local",
          "entry", "sl", "tp", "exit", "exit_reason", "net", "risk", "r", "held_min", "setup", "grade", "note",
          "reviewed"]
EDITABLE = ("setup", "grade", "note", "reviewed")
CLOSING = ("out", "out_by", "inout")


def _f(x: str) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def remember_open_positions(export_dir: str, account_key: str) -> None:
    """Records each open position's first stop and target (many traders add the stop after opening)."""
    seen = load_json(SEEN, {})
    changed = False
    for p in read_csv(os.path.join(export_dir, "positions.csv")):
        k = f"{account_key}:{p['ticket']}"
        cur = seen.get(k)
        if cur is None or (not _f(cur.get("sl")) and _f(p.get("sl"))):
            seen[k] = {"sl": p.get("sl", ""), "tp": p.get("tp", ""), "first_seen": p.get("time_open", "")}
            changed = True
    if changed:
        save_json(SEEN, seen)


def build_trades(deals: List[dict], account_key: str, offset: float, quotes: dict, seen: dict) -> List[dict]:
    """Closed positions from the deal history, one dict per position."""
    by_pos: Dict[str, List[dict]] = {}
    for d in deals:
        if d.get("type") in ("buy", "sell") and d.get("position") not in (None, "", "0"):
            by_pos.setdefault(d["position"], []).append(d)
    out = []
    for pos, ds in by_pos.items():
        ds.sort(key=lambda d: d["time"])
        ins = [d for d in ds if d["entry"] == "in"]
        outs = [d for d in ds if d["entry"] in CLOSING]
        if not ins or not outs:
            continue
        vin, vout = sum(_f(d["volume"]) for d in ins), sum(_f(d["volume"]) for d in outs)
        if abs(vin - vout) > 1e-6:
            continue                                   # partly closed: still open
        entry = sum(_f(d["price"]) * _f(d["volume"]) for d in ins) / vin
        exitp = sum(_f(d["price"]) * _f(d["volume"]) for d in outs) / vout
        sym, side = ins[0]["symbol"], ins[0]["type"]
        first = seen.get(f"{account_key}:{pos}", {})
        sl = next((_f(d["sl"]) for d in ins if _f(d["sl"])), 0.0) or _f(first.get("sl"))
        tp = next((_f(d["tp"]) for d in ins if _f(d["tp"])), 0.0) or _f(first.get("tp"))
        net = sum(_f(d["profit"]) + _f(d["commission"]) + _f(d["swap"]) + _f(d.get("fee")) for d in ds)
        q = quotes.get(sym)
        risk = q.money(entry - sl, vin) if (q and sl) else 0.0
        t_open, t_close = parse_time(ins[0]["time"]), parse_time(outs[-1]["time"])
        digits = q.digits if q else 5
        out.append({
            "id": f"{account_key}:{pos}", "account": account_key, "symbol": sym, "side": side, "lots": f"{vin:.2f}",
            "open_server": ins[0]["time"], "close_server": outs[-1]["time"],
            "open_local": local_time(t_open, offset).strftime("%Y-%m-%d %H:%M"),
            "close_local": local_time(t_close, offset).strftime("%Y-%m-%d %H:%M"),
            "entry": f"{entry:.{digits}f}", "sl": f"{sl:.{digits}f}" if sl else "", "tp": f"{tp:.{digits}f}" if tp else "",
            "exit": f"{exitp:.{digits}f}", "exit_reason": outs[-1].get("reason", ""), "net": f"{net:.2f}",
            "risk": f"{risk:.2f}" if risk else "", "r": f"{net / risk:+.2f}" if risk else "",
            "held_min": str(int((t_close - t_open).total_seconds() // 60)),
            "setup": "", "grade": "", "note": "", "reviewed": "",
        })
    return out


def read_trades() -> List[dict]:
    return read_csv(TRADES)


def _write(rows: List[dict], labels: Dict[str, str]) -> None:
    os.makedirs(JOURNAL, exist_ok=True)
    rows.sort(key=lambda r: r["close_server"])
    tmp = TRADES + ".tmp"
    with open(tmp, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    replace(tmp, TRADES)
    lines = ["# Trade journal", "",
             "Generated from journal/trades.csv (MT5's history). Times are your computer's. R uses the initial stop. "
             "AI reviews and notes: [reviews.md](reviews.md).", "",
             "| Closed | Account | Symbol | Side | Lots | Entry | SL | Exit | Exit by | Net | R | Held | Setup | Grade | Note |",
             "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in reversed(rows[-300:]):
        lines.append(f"| {r['close_local']} | {labels.get(r['account'], r['account'])} | {r['symbol']} | {r['side']} | "
                     f"{r['lots']} | {r['entry']} | {r['sl']} | {r['exit']} | {r['exit_reason']} | {r['net']} | {r['r']} | "
                     f"{r['held_min']}m | {r['setup']} | {r['grade']} | {r['note']} |")
    with open(TABLE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    if not os.path.exists(REVIEWS):
        with open(REVIEWS, "w", encoding="utf-8") as f:
            f.write("# Trade reviews and notes\n\nNewest at the bottom. Written by the AI review "
                    "(prompts/review.md) and by you.\n")


def update(cfg: dict, account_key: str, offset: float) -> List[dict]:
    """Merges every account's closed trades into trades.csv. Returns the trades new since the last update (none on the
    very first run, which imports the history quietly)."""
    export_dir = cfg["export_dir"]
    remember_open_positions(export_dir, account_key)
    seen = load_json(SEEN, {})
    quotes = read_quotes(export_dir)
    with locked(TRADES):
        first_run = not os.path.exists(TRADES)
        old = {r["id"]: r for r in read_trades()}
        rows = dict(old)
        for path in glob.glob(os.path.join(export_dir, "history_*.csv")):
            key = re.sub(r"^history_|\.csv$", "", os.path.basename(path))
            for t in build_trades(read_csv(path), key, offset, quotes, seen):
                prev = old.get(t["id"])
                if prev:
                    for k in EDITABLE:
                        t[k] = prev.get(k, "")
                    if not t["r"] and prev.get("r"):          # keep a risk computed while quotes were available
                        t["risk"], t["r"] = prev["risk"], prev["r"]
                rows[t["id"]] = t
        new = [] if first_run else [t for i, t in rows.items() if i not in old]
        if rows != old or first_run:
            try:
                _write(list(rows.values()), cfg.get("journal", {}).get("account_labels", {}))
            except PermissionError:
                log("journal/trades.csv is locked by another program (Excel?): close it; the journal catches up then")
                return []
    return sorted(new, key=lambda t: t["close_server"])


def tag(trade_id: str, values: Dict[str, str], cfg: Optional[dict] = None) -> dict:
    bad = [k for k in values if k not in EDITABLE]
    if bad:
        raise SystemExit(f"Only {', '.join(EDITABLE)} can be set (not {', '.join(bad)}).")
    with locked(TRADES):
        rows = read_trades()
        hit = [r for r in rows if r["id"] == trade_id or r["id"].endswith(":" + trade_id)]
        if len(hit) != 1:
            raise SystemExit(f"No single trade matches {trade_id!r}.")
        for k, v in values.items():
            hit[0][k] = " ".join(v.replace("|", "/").split())
        _write(rows, (cfg or {}).get("journal", {}).get("account_labels", {}))
    return hit[0]


def summary_line(t: dict, label: str = "") -> str:
    r = f"{t['r']}R " if t["r"] else ""
    return (f"{t['symbol']} {t['side']} closed {r}({float(t['net']):+.2f}) · {t['exit_reason'] or 'closed'} · "
            f"held {t['held_min']} min{' · ' + label if label else ''}")


def recent(n: int = 10) -> List[dict]:
    return read_trades()[-n:]


def now_local() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M")
