# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog.

## [Unreleased]

- Updated README CLI examples to use `--allowed-buttons`.
- Clarified match behavior differences between `--bot-play` (fast enemy) and non-bot mode (autoplay).
- Expanded README selector docs with bot-play selectors (`#fastEnemyBtn`, `#attackBtn`, `button.skillCard`).
- Marked skill-based automated play achievements support as implemented in roadmap section.

## [2026-06-30]

### Added
- Switched CLI headless mode input from positional `true` to `--headless` flag.
- Game-specific documentation for Demonic Scans PvP flow.
- Selector reference section for current automation targets.
- Troubleshooting guidance for login, tokens, matchmaking, and match-status detection.

### Changed

- Rewrote README to match current `pvp_bot.py` behavior.
- Updated setup instructions to use project-based install (`pip install -e .`) and Playwright browser install.
- Documented the current state-machine loop used by automation.
