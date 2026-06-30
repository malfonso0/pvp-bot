# PVP Bot

Browser automation for Demonic Scans PvP using Playwright + BeautifulSoup.

## About The Game

This bot is built for the PvP mode at:

- Dashboard: https://demonicscans.org/game_dash.php
- PvP page: https://demonicscans.org/pvp.php

The current game flow this bot expects:

- You enter Solo PvP matchmaking.
- A token is consumed when you start a match.
- The match can be set to Auto Play.
- Match status is shown in a badge (`#matchStatusBadge`) and eventually contains `victory` when done.
- If you win, a rewards continue button (`#continueRewardsBtn`) may appear before returning to PvP.

## What The Bot Does (Latest)

The bot now runs as a state-driven loop:

1. Open browser and navigate dashboard -> PvP.
2. Detect current page state from live HTML.
3. If on PvP:
    - Read `Tokens` from `div.info-pill`.
    - If tokens are `0`, wait 60 seconds and check again.
    - If tokens are available, click solo matchmaking.
4. If on match page:
   - By default (bot-play mode), enable fast enemy with `#fastEnemyBtn` (if not already on).
   - With `--autoplay`, enable autoplay with `#autoPlayBtn`
    - Poll match status until it is no longer `in progress`.
5. After match end:
    - If reward continue button is visible, click it.
    - Click `a.back-btn` to return to PvP.
6. Repeat forever (unless you set a max iteration count in code).

It also includes:

- Automatic retries for clicks.
- Basic recovery for server errors (reload on HTTP 5xx).
- Logging for each state transition and iteration.

## Requirements

- Python 3.12+
- Chromium for Playwright

## Setup

Install project dependencies:

```bash
pip install -e .
playwright install chromium
```

Optional login credentials (if session is not already active):

```powershell
$env:GAME_USERNAME = "your_email_or_username"
$env:GAME_PASSWORD = "your_password"
```

If these are not set, the bot assumes your session is already logged in.

## Run

Run visible browser (default):

```bash
python pvp_bot.py
```

Run headless:

```bash
python pvp_bot.py --headless
```

Run active bot play during match progress (default behavior):

```bash
python pvp_bot.py
```

Run autoplay mode instead of bot play:

```bash
python pvp_bot.py --autoplay
```

Run bot play with explicit strategy and allowed buttons (Slash is always allowed):

```bash
python pvp_bot.py --strategy balanced_skills --allowed-buttons "Back Stab" "Power Slash"
```

Strategy notes:

- `balanced_skills`: Tries to use all available skills over time. Helpful for achievements.
- `custom`: Placeholder strategy for future rules. Currently redirects to `balanced_skills`.

Allowed buttons notes:

- Accepts space-separated values and comma-separated values.
- Example equivalent inputs:
   - `--allowed-buttons "Back Stab" "Power Slash"`
   - `--allowed-buttons "Back Stab,Power Slash"`
- `Slash` is always allowed as a fallback.

## Selectors Used

Current selectors in code:

- Tokens container: `div.info-pill` containing text `Tokens`
- Solo queue button: `button.js-matchmake[data-ladder="solo"]`
- Continue active match link: `a:has-text("Continue Solo Match")`
- Autoplay button: `#autoPlayBtn`
- Fast enemy button: `#fastEnemyBtn`
- Attack button (bot play): `#attackBtn`
- Skill buttons (bot play): `button.skillCard`
- Match status: `#matchStatusBadge`
- Reward continue button: `#continueRewardsBtn`
- Return button: `a.back-btn`

If the game UI changes, update selectors in `pvp_bot.py`.

## Troubleshooting

- Bot cannot find match button:
   Check `button.js-matchmake[data-ladder="solo"]` and `Continue Solo Match` text.
- Bot never detects match end:
   Confirm `#matchStatusBadge` exists and contains expected status text.
- Token read fails:
   Verify token display is still inside an `info-pill` block with `Tokens` label.
- Login does not submit:
   Check login selectors in `login()` (`input[name="email"]`, `input[name="password"]`, `input[name="submit"]`).

## Notes

- Use `headless=False` while tuning selectors so you can watch behavior.
- This script is intended for personal automation. Use responsibly and at your own risk.

## Future Implementations

- [x] Automated play using skills to help complete new skill achievements (implemented by default with strategy selection).
- [ ] Party PvP autoplay.
- [ ] Party PvP automated play.

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for full project history.
