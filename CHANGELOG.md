# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog.

## [Unreleased]

- Changed match-mode CLI behavior to use `--autoplay` for autoplay mode; bot-play is now the default when the flag is not provided.
- Updated examples and debug launch configuration to reflect the new default bot-play + optional `--autoplay` flow.
- Added bot-play runtime mode controls with strategy and skill filtering flags: `--strategy` and `--allowed-buttons`.
- Added skill-selection pipeline for live matches, including skill metadata parsing and allowed-button filtering (with `Slash` always allowed).
- Added balanced skill strategy tracking/rotation and a `custom` placeholder strategy that currently delegates to balanced behavior.
- Added match state handling for fast-enemy mode (`#fastEnemyBtn`) and active turn-based attack flow (`#attackBtn`, `button.skillCard`).
- Added VS Code debug launch defaults for bot-play usage (`envFile` and bot-play args in `.vscode/launch.json`).
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
