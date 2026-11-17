# TraderClaw kit

Your MetaTrader 5 charts, wired up to an AI agent. Session and day/week levels drawn for you, phone alerts when they're
taken, alerts written for **your** strategy by Claude, and a journal that fills itself and gets every trade reviewed.

**Read-only by design.** Nothing here can place, change or close a trade. It reads MT5, draws lines and sends
notifications. You make every trade.

## What you get

- **Levels on your MT5 charts:** previous week high/low (PWH/PWL), previous day high/low (PDH/PDL), yesterday's and
  today's Tokyo / London / New York session highs and lows. Amber while untaken, grey dotted once taken.
- **The same levels on TradingView:** a Pine script with matching hours.
- **Phone alerts:** when a level is taken, and whether the next 15-minute candle closed back inside (a sweep) or beyond
  (accepted). Through the MetaTrader app's push notifications, or Telegram.
- **Alerts for your strategy:** tell your agent how you trade; it writes your strategy down, then builds alerts for the
  parts a machine can check ("London takes the Tokyo low and an M5 closes back inside"), replays them on recent candles
  so you see what you'd have got, and switches them on.
- **A journal that writes itself:** every closed trade from MT5's history, with R from your initial stop.
- **AI trade reviews:** after each trade (or when you ask), Claude checks it against your own rules: what was good,
  what broke the plan, one lesson, a grade. Plus stats by symbol, session, setup and grade.

## Before you start

- **MetaTrader 5 desktop**, logged in to your account (a demo is fine): Windows, or the official Mac app. Linux under
  Wine works, best effort.
- **The MetaTrader 5 phone app** on the same account, for push notifications.
- **Python 3.9+**. Windows: python.org, tick "Add python.exe to PATH" in the installer. Mac: `python3 --version`.
- **An AI coding agent** for the guided setup, strategy alerts and reviews:
  [Claude Code](https://code.claude.com/docs/en/setup) (needs a Claude subscription or API credit; on Windows also
  [Git for Windows](https://git-scm.com/download/win)), or another agent (see "Other agents" below). The levels,
  alerts and journal also work without any AI: [docs/setup.md](docs/setup.md).

**What has to stay running:** MT5, open and logged in, and the engine (setup makes it start with your computer), on a
computer that's awake. One kit covers one MT5 installation.

## Quick start (with Claude Code, about 20 minutes)

```bash
git clone https://github.com/parth-koshta/traderclaw-kit ~/traderclaw-kit
cd ~/traderclaw-kit
claude
```

No Git? Use **Code > Download ZIP** on GitHub, unzip, and open a terminal in the folder that contains this README (a ZIP
can unpack into two nested `traderclaw-kit-main` folders). On a Mac keep it in your home folder, not in Documents,
Desktop, Downloads or iCloud (macOS blocks background programs there).

Then say: **"set me up"**. The agent finds MT5, installs and compiles the service, configures your symbols and session
hours, tests a phone notification, and sets it to start with your computer. You click where it tells you to in MT5.

Afterwards, just talk to it:
- "Learn my strategy" → it interviews you and writes `my-strategy/STRATEGY.md` (stays on your computer).
- "Alert me when London sweeps the Asia low on EURUSD and an M5 closes back inside."
- "Review my trades this week." / "Journal this: I closed early because of news."
- "Is everything working?"

**Other agents** (Codex, Cursor, Gemini CLI, Copilot...): open the folder in your agent and say: *"Read AGENTS.md, then
set me up by following .claude/skills/setup/SKILL.md step by step."* Expect it to ask permission for the MT5 steps.

**By hand, no agent:** [docs/setup.md](docs/setup.md). Problems: [docs/troubleshooting.md](docs/troubleshooting.md).
Updating or removing: [docs/update-and-uninstall.md](docs/update-and-uninstall.md).

## How it works

```
MT5 ── TraderClaw service ──► export folder (candles, positions, history)  ◄── reads ── traderclaw engine (Python)
 ▲        │                                                                                 │
 │        └─ draws draw_levels.csv on your charts, pushes notify.tsv to your phone ◄────────┘ writes
 └─ you trade                                              journal/ ◄── AI review (Claude Code, headless)
```

Details: [docs/how-it-works.md](docs/how-it-works.md) · alert rules: [rules/README.md](rules/README.md) · journal and
reviews: [docs/journal-and-review.md](docs/journal-and-review.md) · TradingView: [docs/tradingview.md](docs/tradingview.md)
· safety and privacy: [docs/safety.md](docs/safety.md).

## Costs

The kit is free (MIT). The AI parts use your Claude plan or API credit: setup and interviews are ordinary chats. The
automatic trade review is off by default; switched on, each review is one short headless run (a one-trade review cost
$0.16 on Sonnet in testing), capped by `review_budget_usd` in `config.json`.

## Disclaimer

Information and tooling only, not financial advice. Trading leveraged products can lose more than you expect; past
alerts and reviews don't predict results. Check your broker's or prop firm's rules on third-party tools before using it.
