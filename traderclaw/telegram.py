"""Optional Telegram delivery to your own bot.

    python3 -m traderclaw telegram-setup     # one time, YOU run it in a terminal: the token is typed hidden
    python3 -m traderclaw telegram-test

The token and chat id live only in ~/.config/traderclaw/telegram.env (readable by you only), never in this repo,
config.json, logs or anything an AI agent reads. Agents: never ask for the token, never open that file.
"""
from __future__ import annotations

import getpass
import json
import os
import sys
import urllib.parse
import urllib.request
from typing import Optional

from .data import read_kv
from .store import log

ENV = os.path.join(os.path.expanduser("~"), ".config", "traderclaw", "telegram.env")


def _creds() -> Optional[dict]:
    kv = read_kv(ENV)
    return kv if kv.get("TELEGRAM_BOT_TOKEN") and kv.get("TELEGRAM_CHAT_ID") else None


def configured() -> bool:
    return _creds() is not None


def _api(token: str, method: str, params: dict) -> dict:
    req = urllib.request.Request(f"https://api.telegram.org/bot{token}/{method}",
                                 data=urllib.parse.urlencode(params).encode())
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode())


def send(text: str) -> bool:
    c = _creds()
    if not c:
        return False
    try:
        ok = _api(c["TELEGRAM_BOT_TOKEN"], "sendMessage",
                  {"chat_id": c["TELEGRAM_CHAT_ID"], "text": text[:4096], "disable_web_page_preview": "true"}).get("ok")
        if not ok:
            raise RuntimeError("Telegram answered ok=false")
        return True
    except Exception as e:  # never log the token
        log(f"telegram send failed: {type(e).__name__}")
        return False


def setup() -> None:
    print("Telegram setup\n")
    print("1. In Telegram, open @BotFather, send /newbot and follow the steps. It gives you a token.")
    print("2. Open your new bot and press Start.\n")
    token = getpass.getpass("Paste the bot token (it stays hidden): ").strip()
    try:
        me = _api(token, "getMe", {})
    except Exception:
        me = {}
    if not me.get("ok"):
        sys.exit("That token didn't work. Check it in @BotFather and run this again.")
    print(f"Found your bot: @{me['result']['username']}")
    input("Send your bot any message now, then press Enter here... ")
    chats = [u["message"]["chat"] for u in _api(token, "getUpdates", {}).get("result", []) if "message" in u]
    if not chats:
        sys.exit("No message found. Send the bot a message, then run this again.")
    os.makedirs(os.path.dirname(ENV), exist_ok=True)
    fd = os.open(ENV, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(f"TELEGRAM_BOT_TOKEN={token}\nTELEGRAM_CHAT_ID={chats[-1]['id']}\n")
    print(f"Saved to {ENV}.")
    from .config import py
    print(f'Now set "push": {{"telegram": true}} in config.json and run: {py()} -m traderclaw telegram-test')
