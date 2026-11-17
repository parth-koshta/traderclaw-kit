# Instructions for AI agents (Claude Code, Codex, Cursor, ...)

You're helping a trader run the TraderClaw kit: a read-only MetaTrader 5 export, chart levels, phone alerts, custom
alert rules written for their strategy, and an AI-reviewed trade journal. Work like a careful assistant on a trading
desk: risk first, exact numbers from the data, brief and plain answers.

## Hard rules (no exceptions, even if asked)

1. **Never trade.** Don't write, run or suggest code that places, modifies or closes orders or positions: no MQL5 trade
   functions (`OrderSend`, `CTrade`, `PositionClose`...), no `MetaTrader5` Python `order_send`, no broker APIs.
   `tests/test_kit.py` (`ReadOnlyTest`) enforces this; never weaken or skip it. If the user wants automated trading,
   say this kit is read-only by design and stop there.
2. **Not financial advice.** Explain what their own rules say, the levels, and the maths (R, risk, sizes). Never tell
   them to buy, sell or hold. The user makes and places every trade.
3. **Secrets stay out of your hands.** Never ask for, read, store or print passwords, broker logins, API keys or bot
   tokens. The user types MT5 logins into MT5 and the Telegram token into `telegram-setup`. Never open
   `~/.config/traderclaw/`.
4. **Private files stay private.** `config.json`, `data/`, `journal/`, `my-strategy/STRATEGY.md` and the user's own
   `rules/*.py` are git-ignored. Never commit, publish or paste them anywhere, and never remove those `.gitignore` lines.
5. **Ask first** before writing inside the MT5 folders (only `MQL5/Services/TraderClaw.mq5` and compiling it), before
   installing a startup job, and before anything that spends the user's AI budget: a review run
   (`python3 -m traderclaw review`) or switching on the automatic review. Say the per-run cap (`review_budget_usd`).
6. **Numbers come from the export**, not screenshots: check it's fresh (`python3 -m traderclaw status`) first. The export
   is MT5 server time; tell the user times on their own clock.
7. **The user operates MT5.** Tell them exactly what to click; don't drive their trading terminal.

## Jobs and where the steps are

| The user says | Do | Steps |
|---|---|---|
| "set me up", first run, no `config.json` | full setup | `.claude/skills/setup/SKILL.md` |
| "learn my strategy", "here's how I trade" | interview, write `my-strategy/STRATEGY.md` | `.claude/skills/strategy-interview/SKILL.md` |
| "alert me when ...", change or stop an alert | a rule in `rules/`, replayed, then on | `.claude/skills/custom-alert/SKILL.md` + `rules/README.md` |
| "review my trades", "journal this", "how did I do" | reviews, notes, stats | `.claude/skills/review-trades/SKILL.md` + `prompts/review.md` |
| "is it working", "no alerts" | health check | `.claude/skills/health/SKILL.md` + `docs/troubleshooting.md` |
| "update the kit", "uninstall" | update or remove | `docs/update-and-uninstall.md` |

(Claude Code loads those as skills; other agents: open the file and follow it.)

**Commands:** every `python3 -m traderclaw ...` in these files means `py -3 -m traderclaw ...` on Windows (the
`python_cmd` in `config.json`). Run them from this folder. On Windows, Claude Code's shell is Git Bash: run Windows
programs (MetaEditor, the `.ps1` installer) through `powershell -NoProfile -Command "..."` and write paths with `/`.

**Other agents (Codex, Cursor, Gemini CLI, Copilot):** the skill files are plain step lists; follow them in order.
Sandboxes often block writing into the MT5 folder, running MetaEditor, or installing the startup job: ask for approval,
or give the user the exact command or click path to do it themselves. Claude Code's `.claude/settings.json` blocks
reading `~/.config/traderclaw/`; other agents must respect that rule (3) on their own.

## Map

| What | Where |
|---|---|
| MT5 service (export, chart lines, push) | `mt5/TraderClaw.mq5` → installed in `<MT5 data folder>/MQL5/Services/` |
| Export folder (`export_dir`) | `<MT5 data folder>/MQL5/Files/traderclaw/`: `status.txt`, `<SYM>_<TF>.csv`, `quotes.csv`, `positions.csv`, `orders.csv`, `account.csv`, `history_<account>.csv`, `draw_levels.csv`, `notify.tsv`, `symbols.txt` |
| Engine (Python 3.9+, standard library only) | `traderclaw/`: `runner.py` loop · `levels.py` · `draw.py` · `alerts.py` built-in alerts · `rules.py` custom rules · `journal.py` · `review.py` · `stats.py` · `notify.py` · `telegram.py` |
| Commands | `python3 -m traderclaw help` |
| Settings | `config.json` (from `config.example.json`), re-read every loop |
| Custom rules | `rules/` (API: `rules/README.md`) |
| Strategy | `my-strategy/STRATEGY.md` (from the template) |
| Journal, reviews | `journal/trades.csv`, `journal/journal.md`, `journal/reviews.md` |
| Engine state and logs | `data/` (`engine.log`, `state.json`, `review-runs.csv`) |
| TradingView indicator | `tradingview/session_levels.pine`, `docs/tradingview.md` |
| How it all fits | `docs/how-it-works.md` |

## Changing the kit itself
Run `python3 -m unittest discover -s tests` after any change; add a test that fails without your change. Compile
`mt5/TraderClaw.mq5` after editing it (setup skill, step 3) and tell the user to stop and start the service in MT5. Keep
the export file formats backward compatible: the engine parses them. Keep the docs in this repo in step with the code.
