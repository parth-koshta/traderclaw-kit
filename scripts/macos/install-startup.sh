#!/bin/bash
# Starts the TraderClaw engine at login (a LaunchAgent; restarted if it stops) and checks that it runs.
# From the kit folder:  bash scripts/macos/install-startup.sh
# Uninstall: docs/update-and-uninstall.md
set -euo pipefail
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
PY="$(command -v python3 || true)"
[ -f "$REPO/config.json" ] || { echo "Create config.json first (docs/setup.md, step 3)."; exit 1; }
[ -n "$PY" ] && "$PY" -c 'import sys; sys.exit(sys.version_info < (3, 9))' \
  || { echo "Python 3.9+ not found (python3). Install it from python.org, then run this again."; exit 1; }

# macOS blocks background programs from Documents, Desktop, Downloads and iCloud Drive: the engine would die quietly.
case "$REPO" in
  "$HOME/Documents"*|"$HOME/Desktop"*|"$HOME/Downloads"*|"$HOME/Library/Mobile Documents"*)
    echo "This folder ($REPO) is one macOS protects from background programs."
    echo "Move the kit first, e.g.:  mv \"$REPO\" ~/traderclaw-kit  then run this script from there."
    exit 1 ;;
esac

mkdir -p "$REPO/data" "$HOME/Library/LaunchAgents"
DEST="$HOME/Library/LaunchAgents/com.traderclaw.engine.plist"
# The PATH lets a background AI review find the `claude` command.
sed -e "s#__PYTHON__#$PY#g" -e "s#__REPO__#$REPO#g" -e "s#__PATH__#$PATH#g" \
  "$REPO/scripts/macos/com.traderclaw.engine.plist" > "$DEST"
LOG="$REPO/data/engine.log"
BEFORE=$( [ -f "$LOG" ] && stat -f %m "$LOG" || echo 0 )
launchctl bootout "gui/$(id -u)/com.traderclaw.engine" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" "$DEST"
echo "Installed: $DEST"
echo "Checking that the engine runs (up to 45 s)..."
for _ in $(seq 45); do
  sleep 1
  if [ -f "$LOG" ] && [ "$(stat -f %m "$LOG")" -gt "$BEFORE" ]; then
    echo "Running. Last log line: $(tail -1 "$LOG")"
    exit 0
  fi
done
echo "No new line in data/engine.log yet. Errors, if any:"
tail -5 "$REPO/data/engine.err.log" 2>/dev/null || true
echo "Run 'python3 -m traderclaw once' in this folder to see what's wrong."
exit 1
