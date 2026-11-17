"""Settings: config.json at the repo root (copy config.example.json). Re-read on every loop, so edits apply within
seconds without a restart."""
from __future__ import annotations

import copy
import json
import os
from typing import Any, Dict, Optional

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(REPO, "data")             # engine state and logs (git-ignored)
JOURNAL = os.path.join(REPO, "journal")       # your trades and reviews (git-ignored)
RULES = os.path.join(REPO, "rules")           # your custom alert rules (git-ignored, except the examples)
STRATEGY = os.path.join(REPO, "my-strategy", "STRATEGY.md")
CONFIG = os.path.join(REPO, "config.json")

DEFAULTS: Dict[str, Any] = {
    "export_dir": "",
    "python_cmd": "python3",
    "symbols": ["EURUSD", "GBPUSD", "XAUUSD"],
    # Server (MT5) time, hours 0-24, each from < to. The defaults suit brokers on New York time + 7 (most of them).
    "sessions": [
        {"name": "Tokyo", "from": 3, "to": 10},
        {"name": "London", "from": 10, "to": 15},
        {"name": "NY", "from": 15, "to": 24},
    ],
    "levels": {"previous_week": True, "previous_day": True, "previous_day_sessions": True, "today_sessions": True},
    "alerts": {
        "level_taken": True,          # a level traded through for the first time
        "close_after_take": True,     # the first M15 close after that: back inside (a sweep) or beyond (accepted)
        "families": ["PW", "PD", "Session"],   # which levels alert: PW, PD, Session (today), PrevSession (yesterday's)
        "session_open": False,        # a push at each session's open listing the nearest untaken levels
    },
    "push": {"mt5": True, "telegram": False},
    "journal": {
        "enabled": True,
        "account_labels": {},         # account_key (status.txt) -> your name for it, e.g. {"Broker-Server_1234": "Live"}
        "auto_review": False,         # an AI review of every trade right after it closes (needs Claude Code)
        "review_model": "sonnet",
        "review_budget_usd": 1.0,     # the most one review run may spend
    },
    "loop_seconds": 15,
    "stale_after_seconds": 180,
}


class ConfigError(Exception):
    pass


def py() -> str:
    """How to run Python on this computer, for messages: `py -3` on Windows, `python3` elsewhere."""
    return "py -3" if os.name == "nt" else "python3"


def _merge(base: dict, over: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in over.items():
        out[k] = _merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else v
    return out


def load(path: Optional[str] = None, require_export: bool = True) -> dict:
    path = path or CONFIG
    if not os.path.exists(path):
        raise ConfigError("No config.json yet. Copy config.example.json to config.json, or ask your agent to run setup.")
    try:
        with open(path, encoding="utf-8-sig") as f:
            cfg = _merge(DEFAULTS, json.load(f))
    except ValueError as e:
        where = f" (line {e.lineno}, column {e.colno})" if isinstance(e, json.JSONDecodeError) else ""
        raise ConfigError(f"config.json isn't valid JSON{where}: {e}. Check commas and quotes; write folder paths with "
                          f"/ (C:/Users/...), not \\.")
    cfg["export_dir"] = os.path.expanduser(cfg.get("export_dir") or "")
    if require_export and (not cfg["export_dir"] or "<" in cfg["export_dir"]):
        raise ConfigError(f"export_dir isn't set. Run `{py()} -m traderclaw find-mt5` and copy the export_dir line it "
                          f"prints into config.json.")
    for s in cfg["sessions"]:
        if not (0 <= s["from"] < s["to"] <= 24):
            raise ConfigError(f"Session {s['name']}: hours must be server time with 0 <= from < to <= 24.")
    return cfg


def python_cmd(cfg: dict) -> str:
    return cfg.get("python_cmd") or "python3"
