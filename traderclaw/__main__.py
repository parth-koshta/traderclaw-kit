"""Command line. Run from the repo folder:  python3 -m traderclaw <command>   (Windows: py -3 -m traderclaw <command>)

  status                  is everything working? (export age, account, symbols, rules, journal, review)
  find-mt5                where MT5's data folders are, and the export_dir to put in config.json
  once | run              one engine pass | the engine forever (the startup job runs this)
  levels [SYMBOL]         today's levels, taken or untaken
  candles SYM TF [--from "YYYY.MM.DD HH:MM"] [--to ...] [--last N]    candles from the export (server time)
  notify [--kind K] TEXT  send a phone notification (kinds: level, alert, session, trade, system)
  telegram-setup          one-time Telegram bot setup (you run it; the token is typed hidden)
  telegram-test           send a Telegram test message
  journal                 update the journal and show the latest trades
  journal tag ID k=v ...  set setup, grade, note or reviewed on a trade
  stats [--days N] [--account KEY]   win rate, R and expectancy, by symbol/session/setup/grade/weekday
  replay RULE.py [--days N] [--symbol SYM]   when a rule would have fired over the exported history
  review [ID ...]         AI-review queued trades (or the given ones) now
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime

from . import __version__, config


def _cfg(require_export: bool = True) -> dict:
    try:
        return config.load(require_export=require_export)
    except config.ConfigError as e:
        sys.exit(str(e))


def cmd_status() -> None:
    from . import rules, journal, review, telegram
    from .data import read_status
    from .store import load_json
    cfg = _cfg()
    ex = cfg["export_dir"]
    print(f"TraderClaw kit {__version__}")
    print(f"export_dir: {ex}" + ("" if os.path.isdir(ex) else "  (NOT FOUND)"))
    st = read_status(ex) if os.path.isdir(ex) else None
    if not st:
        print("MT5 service: no status.txt. Start the TraderClaw service in MT5 (Navigator > Services).")
    else:
        age = st.age_seconds()
        ok = age <= cfg["stale_after_seconds"]
        print(f"MT5 service: v{st.version or '?'}, last export {st.server_time} server time, {int(age)} s ago "
              f"{'(OK)' if ok else '(STALE: is MT5 open? markets closed?)'}")
        print(f"account: {st.account_key} at {st.company}; server time = UTC{st.offset_hours:+g}")
        missing = [s for s in cfg["symbols"] if not os.path.exists(os.path.join(ex, f"{s}_M5.csv"))]
        print(f"symbols: {', '.join(cfg['symbols'])}" + (f"  (no candles yet for {', '.join(missing)}: check the "
                                                          f"exact names in MT5's Market Watch)" if missing else ""))
        if st.errors:
            print(f"service errors: {st.errors}")
    push = cfg["push"]
    print(f"push: MT5 {'on' if push.get('mt5') else 'off'}, Telegram "
          f"{'on' if push.get('telegram') else 'off'}{' (not set up)' if push.get('telegram') and not telegram.configured() else ''}")
    files = rules.rule_files()
    on = []
    for p in files:
        try:
            r = rules.load_rule(p)
            on.append(f"{r.key}{'' if r.enabled else ' (off)'}")
        except Exception as e:
            on.append(f"{os.path.basename(p)} (BROKEN: {e})")
    print(f"rules: {', '.join(on) or 'none'}")
    trades = journal.read_trades()
    j = cfg["journal"]
    print(f"journal: {len(trades)} trades; auto review {'on' if j.get('auto_review') else 'off'}"
          f"{', queued ' + str(len(load_json(review.QUEUE, []))) if j.get('auto_review') else ''}")
    log = os.path.join(config.DATA, "engine.log")
    if os.path.exists(log):
        with open(log, encoding="utf-8") as f:
            last = [line.strip() for line in f if line.strip()][-1:]
        print(f"engine log: {last[0] if last else '(empty)'}")
    else:
        print("engine log: none yet (the engine hasn't run)")


def cmd_levels(symbol: str = "") -> None:
    from .data import load_all, read_quotes, read_status, guess_info, local_time
    from .levels import chart_levels
    cfg = _cfg()
    st = read_status(cfg["export_dir"])
    if not st:
        sys.exit("No export yet.")
    quotes = read_quotes(cfg["export_dir"])
    for sym in [symbol] if symbol else cfg["symbols"]:
        bars = load_all(cfg["export_dir"], sym)
        if not bars.get("M5"):
            print(f"{sym}: no candles")
            continue
        info = quotes.get(sym) or guess_info(sym, bars["M5"])
        print(f"\n{sym} {info.fmt(bars['M5'][-1].c)}")
        for lv in sorted(chart_levels(bars, st.server_time, cfg["sessions"], cfg["levels"]), key=lambda x: -x.price):
            took = f"taken {local_time(lv.taken_at, st.offset_hours):%H:%M}" if lv.taken_at else "untaken"
            print(f"  {info.fmt(lv.price):>12}  {lv.label:<26} {took}")


def cmd_candles(a: argparse.Namespace) -> None:
    from .data import guess_info, load_bars, parse_time, read_quotes, read_status, local_time
    cfg = _cfg()
    st = read_status(cfg["export_dir"])
    bars = load_bars(cfg["export_dir"], a.symbol, a.tf)
    if not bars:
        sys.exit(f"No {a.symbol} {a.tf} candles in the export (check the symbol name).")
    fmt = (read_quotes(cfg["export_dir"]).get(a.symbol) or guess_info(a.symbol, bars)).fmt
    if a.start:
        bars = [b for b in bars if b.t >= parse_time(a.start)]
    if a.end:
        bars = [b for b in bars if b.t <= parse_time(a.end)]
    if a.last:
        bars = bars[-a.last:]
    off = st.offset_hours if st else 0
    print("server_time,local_time,open,high,low,close,tick_volume")
    for b in bars[:2000]:
        print(f"{b.t:%Y.%m.%d %H:%M},{local_time(b.t, off):%Y-%m-%d %H:%M},{fmt(b.o)},{fmt(b.h)},{fmt(b.l)},{fmt(b.c)},"
              f"{int(b.v)}")


def cmd_journal(rest: list) -> None:
    from . import journal
    from .data import read_status
    cfg = _cfg()
    if rest[:1] == ["tag"]:
        if len(rest) < 3:
            sys.exit('usage: journal tag <id> setup="..." grade=A|B|C note="..." reviewed=yes')
        vals = dict(x.split("=", 1) for x in rest[2:] if "=" in x)
        t = journal.tag(rest[1], vals, cfg)
        print(f"{t['id']}: " + ", ".join(f"{k}={t[k]}" for k in vals))
        return
    st = read_status(cfg["export_dir"])
    if st:
        journal.update(cfg, st.account_key, st.offset_hours)
    rows = journal.recent(10)
    if not rows:
        print("No closed trades yet (the journal fills from MT5's history once the service runs).")
    for r in rows:
        print(f"{r['id']:<28} {r['close_local']}  {r['symbol']:<8} {r['side']:<4} {r['r'] or '  -  ':>6}R "
              f"{float(r['net']):+9.2f}  {r['setup'] or '-':<14} {r['grade'] or '-'}{'  reviewed' if r['reviewed'] else ''}")


def main(argv: list) -> None:
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(__doc__)
        return
    cmd, rest = argv[0], argv[1:]
    if cmd == "version":
        print(__version__)
    elif cmd == "find-mt5":
        from .findmt5 import report
        print(report())
    elif cmd == "status":
        cmd_status()
    elif cmd in ("run", "once"):
        from .runner import run
        run(once=cmd == "once")
    elif cmd == "levels":
        cmd_levels(rest[0] if rest else "")
    elif cmd == "candles":
        p = argparse.ArgumentParser(prog="candles")
        p.add_argument("symbol")
        p.add_argument("tf", choices=["M1", "M5", "M15", "H1", "H4", "D1"])
        p.add_argument("--from", dest="start")
        p.add_argument("--to", dest="end")
        p.add_argument("--last", type=int)
        cmd_candles(p.parse_args(rest))
    elif cmd == "notify":
        from . import notify
        kind = ""
        if rest[:1] == ["--kind"]:
            kind, rest = rest[1], rest[2:]
            if kind not in notify.TAGS:
                sys.exit(f"kind must be one of: {', '.join(notify.TAGS)}")
        if not rest:
            sys.exit('usage: notify [--kind K] "text"')
        notify.send(_cfg(), " ".join(rest), kind)
        print("queued (MT5 pushes within a few seconds while the service runs)")
    elif cmd == "telegram-setup":
        from . import telegram
        telegram.setup()
    elif cmd == "telegram-test":
        from . import telegram
        print("sent" if telegram.send(f"TraderClaw test {datetime.now():%H:%M}") else
              "not sent: run telegram-setup first (see data/engine.log for errors)")
    elif cmd == "journal":
        cmd_journal(rest)
    elif cmd == "stats":
        from . import journal, stats
        p = argparse.ArgumentParser(prog="stats")
        p.add_argument("--days", type=int)
        p.add_argument("--account")
        a = p.parse_args(rest)
        print(stats.report(journal.read_trades(), _cfg(), a.days, a.account))
    elif cmd == "replay":
        from . import rules
        from .data import read_status
        p = argparse.ArgumentParser(prog="replay")
        p.add_argument("rule")
        p.add_argument("--days", type=float, default=3)
        p.add_argument("--symbol", action="append")
        a = p.parse_args(rest)
        cfg = _cfg()
        st = read_status(cfg["export_dir"])
        off = st.offset_hours if st else 0
        hits = rules.replay(cfg, a.rule, a.days, a.symbol, off)
        from .data import local_time
        for sym, t, msg in hits:
            print(f"{t:%Y.%m.%d %H:%M} server ({local_time(t, off):%a %H:%M} local)  {sym}  {msg}")
        print(f"\n{len(hits)} alert(s) in the last {a.days:g} days of exported candles.")
    elif cmd == "review":
        from . import review
        sys.exit(review.run_now(_cfg(), rest or None))
    else:
        sys.exit(f"unknown command {cmd!r}. Try: {config.py()} -m traderclaw help")


if __name__ == "__main__":
    main(sys.argv[1:])
