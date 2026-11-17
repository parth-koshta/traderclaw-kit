"""Phone notifications.

MT5 push (default): messages go to notify.tsv in the export folder (id, time, text; tab-separated). The TraderClaw MT5
service sends every new id as an MT5 push notification to the MetaTrader app on your phone (MetaQuotes ID, set in
MT5: Tools > Options > Notifications). Telegram (optional): the same text to your own bot, see telegram.py.

    python3 -m traderclaw notify "text"                 # a test, or from your own scripts
    python3 -m traderclaw notify --kind alert "text"
"""
from __future__ import annotations

import os
from datetime import datetime

from .store import locked, replace

KEEP = 100
TAGS = {
    "level": "💧 LEVEL",     # a session/day/week level was taken, or how the M15 closed after it
    "alert": "🔔 ALERT",     # one of your custom rules fired
    "session": "🕒 SESSION", # a session opened
    "trade": "🧾 TRADE",     # your trade closed (result), or its AI review
    "system": "⚙️ SYSTEM",   # the kit itself: stale export, a broken rule, a failed review
}


def tag(kind: str, text: str) -> str:
    return f"{TAGS[kind]} {text}" if kind else text


def queue_mt5(export_dir: str, text: str) -> int:
    path = os.path.join(export_dir, "notify.tsv")
    with locked(path):
        rows = []
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                rows = [line.rstrip("\n").split("\t") for line in f][1:]
        rows = [r for r in rows if len(r) >= 3 and r[0].isdigit()]
        next_id = int(rows[-1][0]) + 1 if rows else 1
        rows.append([str(next_id), datetime.now().strftime("%Y-%m-%d %H:%M:%S"), text])
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            f.write("id\ttime\ttext\n")
            f.writelines("\t".join(r) + "\n" for r in rows[-KEEP:])
        replace(tmp, path)
    return next_id


def send(cfg: dict, text: str, kind: str = "") -> None:
    """Send to every channel switched on in config.json "push". Never raises: an alert must not stop the engine."""
    text = " ".join(tag(kind, text).split())
    push = cfg.get("push", {})
    if push.get("mt5", True) and cfg.get("export_dir"):
        try:
            queue_mt5(cfg["export_dir"], text[:245])     # MT5 pushes take 255 UTF-16 units; an emoji takes 2
        except OSError:
            pass
    if push.get("telegram"):
        from . import telegram
        telegram.send(text)
