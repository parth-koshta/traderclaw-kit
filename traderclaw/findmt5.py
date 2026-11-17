"""Finds MetaTrader 5 data folders (the folder that holds MQL5/) on Windows, macOS and Linux (Wine).

    python3 -m traderclaw find-mt5
"""
from __future__ import annotations

import glob
import os
from typing import List

from .data import read_kv


def candidates() -> List[str]:
    home = os.path.expanduser("~")
    pats = []
    appdata = os.environ.get("APPDATA")
    if appdata:                                                   # Windows: one folder per installed terminal
        pats.append(os.path.join(appdata, "MetaQuotes", "Terminal", "*", "MQL5"))
    for root in (os.environ.get("ProgramFiles", r"C:\Program Files"), os.environ.get("ProgramFiles(x86)", "")):
        if root:
            pats.append(os.path.join(root, "*", "MQL5"))          # portable installs
    for prefix in (os.path.join(home, "Library", "Application Support", "net.metaquotes.wine.metatrader5"),  # macOS app
                   os.path.join(home, ".mt5"), os.path.join(home, ".wine")):                               # Linux Wine
        pats.append(os.path.join(prefix, "drive_c", "Program Files", "*", "MQL5"))
        pats.append(os.path.join(prefix, "drive_c", "users", "*", "AppData", "Roaming", "MetaQuotes", "Terminal", "*",
                                 "MQL5"))
    found = []
    for p in pats:
        for d in glob.glob(p):
            if os.path.isdir(os.path.join(d, "Services")) or os.path.isdir(os.path.join(d, "Experts")):
                found.append(os.path.dirname(d))
    return sorted(set(found))


def report() -> str:
    found = candidates()
    if not found:
        return ("No MT5 data folder found. In MT5: File > Open Data Folder shows it; the export folder is "
                "<that folder>/MQL5/Files/traderclaw")
    lines = ["MT5 data folders found (one per installed MetaTrader 5; pick the one you trade on):"]
    for d in found:
        export = os.path.join(d, "MQL5", "Files", "traderclaw")
        st = read_kv(os.path.join(export, "status.txt"))
        origin = ""
        try:
            with open(os.path.join(d, "origin.txt"), encoding="utf-16") as f:
                origin = f.read().strip()
        except (OSError, UnicodeError):
            pass
        state = (f"TraderClaw export running, account at {st.get('account_company', '?')}, "
                 f"last export {st.get('exported_server_time', '?')} server time") if st else "no TraderClaw export yet"
        # Forward slashes work on Windows too, and paste into JSON as they are (backslashes would break it).
        lines.append(f"\n- data folder: {d}" + (f"\n  MT5 installed at: {origin}" if origin else "") + f"\n  {state}"
                     f"\n  for config.json:  \"export_dir\": \"{export.replace(os.sep, '/')}\",")
    return "\n".join(lines)
