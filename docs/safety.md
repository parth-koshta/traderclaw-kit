# Safety and privacy

## It can't trade

- The MT5 service has no trading functions: no `OrderSend`, no `CTrade`, nothing that opens, changes or closes orders.
  Read `mt5/TraderClaw.mq5`: it's one file.
- The Python engine never connects to your broker. It reads files MT5 writes, and writes three back (`draw_levels.csv`,
  `notify.tsv`, `symbols.txt`).
- `tests/test_kit.py` (`ReadOnlyTest`) fails if trading calls are ever added, by you or an AI agent. `AGENTS.md` tells
  agents never to add them.

## Your data stays on your computer

- Git-ignored: `config.json`, `data/`, `journal/`, `my-strategy/STRATEGY.md`, your own `rules/*.py` and their tests. Don't
  remove those lines from `.gitignore` if you publish a fork.
- **Don't keep your own setup in a fork.** GitHub forks of a public repo are public. To back up your journal, strategy and rules, copy those folders somewhere private, or push a clone to a new *private* repo (not a fork). Never upload the folder through GitHub's web "Upload files": it ignores `.gitignore`.
- Your MT5 password never touches the kit. The Telegram bot token (optional) is typed hidden into `telegram-setup` and
  saved in `~/.config/traderclaw/telegram.env`, readable by you only; agents are told never to open it.
- The export folder holds your positions and history: it's inside MT5's own folder, on your computer.

## AI and costs

- Your agent reads your export, journal and strategy file to help you; that content goes to the AI provider you use, as
  with any chat. Don't use the kit with an agent you don't trust with your trading data.
- The automatic review is off by default. Each run is capped by `review_budget_usd` and logged in `data/review-runs.csv`.

## Not advice

Alerts are heads-ups to look at a chart, built from rules you chose; reviews judge trades against your own plan. Nothing
here is financial advice, and nothing predicts what price will do. Check your broker's or prop firm's terms on
third-party tools.
