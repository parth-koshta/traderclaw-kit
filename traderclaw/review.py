"""AI review of closed trades, run by Claude Code in headless mode (`claude -p`), with prompts/review.md.

Automatic (config.json "journal": {"auto_review": true}): when a trade closes, the engine queues it and starts one
background review run at a time. The run may read the repo and the MT5 export, write only inside journal/, and run only
the kit's journal, candles and notify commands. Each run is capped at "review_budget_usd".

By hand, any time:
    python3 -m traderclaw review              # review every queued trade now (in this terminal)
    python3 -m traderclaw review <id> [<id>]  # review given trades (ids from journal/trades.csv)
Or inside Claude Code: "review my trades today" (the review-trades skill).
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from datetime import datetime
from typing import List, Optional

from . import notify
from . import config
from .config import DATA, REPO, python_cmd
from .store import load_json, log, save_json

QUEUE = os.path.join(DATA, "review_queue.json")
FAILED = os.path.join(DATA, "review_failed.json")      # not retried automatically (a retry costs money); `review` does
STATE = os.path.join(DATA, "review_state.json")
RUNNING = os.path.join(DATA, "review_running.json")
RUNS = os.path.join(DATA, "review-runs.csv")
OUT_DIR = os.path.join(DATA, "reviews")
TIMEOUT_MIN = 30

_proc: Optional[subprocess.Popen] = None


def enqueue(ids: List[str]) -> None:
    q = load_json(QUEUE, [])
    q += [i for i in ids if i not in q]
    save_json(QUEUE, q)


def command(cfg: dict, ids: List[str]) -> List[str]:
    claude = shutil.which("claude")
    if not claude:
        raise FileNotFoundError("the `claude` command isn't on PATH (install Claude Code, or set PATH for the engine)")
    py = python_cmd(cfg)
    j = cfg.get("journal", {})
    prompt = (f"Trade review. Follow prompts/review.md exactly for these closed trades (ids in journal/trades.csv): "
              f"{', '.join(ids)}. Local time now {datetime.now():%Y-%m-%d %H:%M}. This is a headless run: nobody is "
              f"watching, so don't ask questions. Finish with one closing line.")
    tools = ["Read", "Glob", "Grep", "Edit(./journal/**)", "Write(./journal/**)",
             f"Bash({py} -m traderclaw journal:*)", f"Bash({py} -m traderclaw candles:*)",
             f"Bash({py} -m traderclaw levels:*)", f"Bash({py} -m traderclaw notify:*)"]
    return [claude, "-p", prompt, "--model", str(j.get("review_model", "sonnet")),
            "--max-budget-usd", str(j.get("review_budget_usd", 1.0)), "--output-format", "json",
            "--add-dir", cfg["export_dir"], "--strict-mcp-config", "--allowedTools", *tools]


def _result(out_path: str) -> dict:
    """The JSON result `claude -p --output-format json` printed (warnings go to the .err file next to it)."""
    try:
        with open(out_path, encoding="utf-8") as f:
            text = f.read()
        return json.loads(text[text.find("{"):]) if "{" in text else {}
    except (OSError, ValueError):
        return {}


def _record(ids: List[str], out_path: str, started: float) -> str:
    r = _result(out_path)
    status = "error" if (r.get("is_error") or not r) else str(r.get("subtype", "error"))
    new = not os.path.exists(RUNS)
    with open(RUNS, "a", encoding="utf-8") as f:
        if new:
            f.write("finished,trades,status,cost_usd,seconds\n")
        f.write(f"{datetime.now():%Y-%m-%d %H:%M:%S},{' '.join(ids)},{status},"
                f"{float(r.get('total_cost_usd') or 0):.4f},{int(time.time() - started)}\n")
    return status


def _start(cfg: dict, ids: List[str]) -> None:
    global _proc
    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = os.path.join(OUT_DIR, f"{datetime.now():%Y%m%d-%H%M%S}.json")
    out = open(out_path, "w", encoding="utf-8")
    err = open(out_path[:-5] + ".err", "w", encoding="utf-8")
    _proc = subprocess.Popen(command(cfg, ids), cwd=REPO, stdout=out, stderr=err, stdin=subprocess.DEVNULL)
    save_json(RUNNING, {"ids": ids, "out": out_path, "started": time.time(), "attempt": 1})
    log(f"review started for {', '.join(ids)}")


def _failed(cfg: dict, ids: List[str], why: str) -> None:
    """Parks the trades for a manual retry and pushes the reason at most once a day (never every loop)."""
    save_json(FAILED, load_json(FAILED, []) + [i for i in ids if i not in load_json(FAILED, [])])
    log(f"review failed for {', '.join(ids)}: {why}")
    st = load_json(STATE, {})
    day = datetime.now().strftime("%Y-%m-%d")
    if st.get("pushed") != day:
        st["pushed"] = day
        save_json(STATE, st)
        notify.send(cfg, f"AI review failed: {why[:120]}. Fix it, then retry: {config.py()} -m traderclaw review",
                    "system")


def tick(cfg: dict) -> None:
    """Called every engine loop: finishes a run that ended, or starts the next one."""
    global _proc
    run = load_json(RUNNING, None)
    if run:
        if _proc is not None and _proc.poll() is None and time.time() - run["started"] < TIMEOUT_MIN * 60:
            return
        if _proc is not None and _proc.poll() is None:
            _proc.kill()
        _proc = None
        status = _record(run["ids"], run["out"], run["started"])
        os.remove(RUNNING)
        if status != "success":
            _failed(cfg, run["ids"], f"{status}, details in {run['out']}")
        return
    if not cfg.get("journal", {}).get("auto_review"):
        return
    q = load_json(QUEUE, [])
    if not q:
        return
    save_json(QUEUE, [])
    try:
        _start(cfg, q)
    except Exception as e:
        _failed(cfg, q, str(e))


def run_now(cfg: dict, ids: Optional[List[str]] = None) -> int:
    """Foreground review (the `review` command): the given ids, or everything queued or failed before."""
    ids = ids or list(dict.fromkeys(load_json(QUEUE, []) + load_json(FAILED, [])))
    if not ids:
        print(f"Nothing queued. Give trade ids (from `{config.py()} -m traderclaw journal`): "
              f"{config.py()} -m traderclaw review <id>")
        return 0
    started = time.time()
    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = os.path.join(OUT_DIR, f"{datetime.now():%Y%m%d-%H%M%S}.json")
    with open(out_path, "w", encoding="utf-8") as out, open(out_path[:-5] + ".err", "w", encoding="utf-8") as err:
        code = subprocess.call(command(cfg, ids), cwd=REPO, stdout=out, stderr=err, stdin=subprocess.DEVNULL)
    status = _record(ids, out_path, started)
    if status == "success":
        save_json(QUEUE, [i for i in load_json(QUEUE, []) if i not in ids])
        save_json(FAILED, [i for i in load_json(FAILED, []) if i not in ids])
        r = _result(out_path)
        print(f"Reviewed {len(ids)} trade(s) for ${float(r.get('total_cost_usd') or 0):.2f}: see journal/reviews.md")
        print(str(r.get("result", ""))[:500])
    else:
        print(f"Review failed ({status}); output in {out_path}")
    return code
