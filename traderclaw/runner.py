"""The engine loop: every few seconds it reads the MT5 export, draws the levels, sends alerts, runs your rules, updates
the journal and starts AI reviews.

    python3 -m traderclaw run     # forever (what the startup job runs)
    python3 -m traderclaw once    # one pass, then exit (for testing)
"""
from __future__ import annotations

import os
import time
import traceback
from datetime import datetime, timedelta, timezone

from . import alerts, config, draw, journal, notify, review, rules
from .data import atr, closed, guess_info, load_all, read_csv, read_quotes, read_status
from .levels import chart_levels
from .store import load_json, log, replace, save_json

STATE = os.path.join(config.DATA, "state.json")


def write_symbols(cfg: dict) -> float:
    """symbols.txt tells the MT5 service which symbols to export, so changing them needs no MT5 step. Returns the
    seconds since the list last changed."""
    path = os.path.join(cfg["export_dir"], "symbols.txt")
    line = ",".join(cfg["symbols"])
    try:
        with open(path, encoding="utf-8") as f:
            if f.read().strip() == line:
                return time.time() - os.path.getmtime(path)
    except OSError:
        pass
    with open(path + ".tmp", "w", encoding="utf-8") as f:
        f.write(line + "\n")
    replace(path + ".tmp", path)
    return 0.0


def tick(cfg: dict, state: dict) -> str:
    """One pass. Returns a one-line status."""
    ex = cfg["export_dir"]
    if not os.path.isdir(ex):
        return f"export folder not found: {ex} (is the TraderClaw service running in MT5?)"
    symbols_age = write_symbols(cfg)
    st = read_status(ex)
    if not st or not st.server_time:
        return "no status.txt yet: start the TraderClaw service in MT5 (Navigator > Services)"
    utc = datetime.now(timezone.utc)
    weekday = utc.weekday() < 5 or (utc.weekday() == 6 and utc.hour >= 22)     # FX is open Sunday 22:00 to Friday 22:00 UTC
    if st.age_seconds() > cfg["stale_after_seconds"]:
        last = state.get("stale_alert", "")
        if weekday and (not last or datetime.now() - datetime.fromisoformat(last) > timedelta(hours=6)):
            state["stale_alert"] = datetime.now().isoformat(timespec="seconds")
            notify.send(cfg, f"MT5 export is {int(st.age_seconds() // 60)} min old. Is MT5 open and the TraderClaw "
                             f"service running?", "system")
        review.tick(cfg)
        return f"export is stale ({int(st.age_seconds())} s old)"
    state.pop("stale_alert", None)
    now, offset = st.server_time, st.offset_hours
    quotes = read_quotes(ex)
    positions = read_csv(os.path.join(ex, "positions.csv"))
    sent = state.setdefault("sent", {})
    all_levels, infos, same, missing = {}, {}, {}, []
    for sym in cfg["symbols"]:
        bars = load_all(ex, sym)
        if not bars.get("M5") or not bars.get("D1"):
            missing.append(sym)
            continue
        info = quotes.get(sym) or guess_info(sym, bars["M5"])
        lv = chart_levels(bars, now, cfg["sessions"], cfg.get("levels"))
        all_levels[sym], infos[sym] = lv, info
        same[sym] = 0.05 * atr(closed(bars["M15"], "M15", now)[-101:], 100)
        for kind, msg in alerts.check(cfg, sym, lv, bars, info, now, offset, sent):
            notify.send(cfg, msg, kind)
            log(f"alert {kind}: {msg}")
        rules.run_live(cfg, sym, bars, info, now, offset, [p for p in positions if p.get("symbol") == sym], state)
    draw.write_levels(ex, all_levels, infos, now, same)
    alerts.prune(sent, now)

    j = cfg.get("journal", {})
    if j.get("enabled", True):
        labels = j.get("account_labels", {})
        new = journal.update(cfg, st.account_key, offset)
        for t in new:
            notify.send(cfg, journal.summary_line(t, labels.get(t["account"], "")), "trade")
            log(f"trade closed: {t['id']}")
        if new and j.get("auto_review"):
            review.enqueue([t["id"] for t in new])
        review.tick(cfg)
    msg = f"ok · {now:%Y-%m-%d %H:%M} server · {len(all_levels)} symbols"
    if missing:
        msg += f" · no candles yet for {', '.join(missing)}: " + (
            "MT5 exports newly listed symbols within about 15 s, so run this again in 30 s" if symbols_age < 60 else
            "check the exact names in MT5's Market Watch (brokers add suffixes like .r or m)")
    return msg


def run(once: bool = False) -> None:
    state = load_json(STATE, {})
    last_msg = ""
    while True:
        try:
            cfg = config.load()
            msg = tick(cfg, state)
            save_json(STATE, state)
        except config.ConfigError as e:
            msg = f"config: {e}"
        except Exception:
            msg = "error: " + traceback.format_exc(limit=4)
        if msg != last_msg:
            log(msg)
            last_msg = msg
        if once:
            print(msg)
            return
        time.sleep(max(5, int(load_json(config.CONFIG, {}).get("loop_seconds", 15))))
