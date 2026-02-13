# CLI Arcade

Collection of small terminal games bundled with a single CLI launcher.

## Requirements
- Python 3.8+

## Quick start
```powershell
# run interactive menu
clia

# list installed console aliases and available games
clia list

# run a game by zero-based index or name
clia run 0
clia run "Byte Bouncer"

# reset highscores for one game or all
clia reset 0
clia reset "Byte Bouncer"
clia reset -y  # skip confirmation

# display highscores for all games or a specific game
clia scores
clia scores 0
clia scores "Byte Bouncer"

# display save directory and executable path
clia find
```

## Commands
- `clia` — interactive terminal menu
- `clia list` — print available games and zero-based indices
- `clia run <index|name>` — run a game directly (index is zero-based)
- `clia reset [<index|name>] [-y|--yes]` — delete highscores for a game or all games
- `clia scores [<index|name>] [-r|--raw]` — display highscores for all games or a specific game, with optional raw JSON output
- `clia find` — display save directory and executable path
- Aliases available: `cli-arcade`

## License
- MIT

# Changelog

All notable changes to this project will be documented in this file.

## 2026.0.0
- Initial release as CLI Game.

## 2026.1.0
- Project renamed to CLI Arcade.
- Packaging metadata updated for PyPI.
- Documentation refresh.

### 2026.1.1
- Updated TITLE ASCII art.
- Added `clia update` command to check for and install updates from PyPI.
  - (YANKED)

### 2026.1.2 (YANKED)
- Version bump for testing the update mechanism.

### 2026.1.3
- Removed `clia update` command.

### 2026.2.0
- Refactoring using `prompt_toolkit` replacing `windows-curses` for better cross-platform compatibility.
- Restore/clear alternate screen on run/exit (no UI artifacts).
- Centralize terminal-size checks in CLI; games expose `MIN_COLS`/`MIN_ROWS`.
- Byte Bouncer & Star Ship: floor + off-screen right wall; left-column bug fixed.
- `ptk`: default-attribute/color emission fix; add helper to exit alt screen.
- Fixed 180 movement glitch in Star Ship.

### 2026.2.1
- Updated key mapping to work with Linux and macOS terminals.

### 2026.3.0
- Added `scores` command to CLI to display highscores for all games or a specific game, with optional raw JSON output.

### 2026.4.0
- Updated `scores` command for better display.
- Added new game - Escape Sequence.
