# CLI Arcade

Collection of small terminal games bundled with a single CLI launcher.

## Requirements
- Python 3.8+

## Quick start
```powershell
# list installed console aliases and available games
clia list

# run interactive menu
clia

# run a game by zero-based index or name
clia run 0
clia run "Byte Bouncer"

# reset highscores for one game or all
clia reset 0
clia reset "Byte Bouncer"
clia reset -y  # skip confirmation
```

## Commands
- `clia` — interactive terminal menu
- `clia list` — print available games and zero-based indices
- `clia run <index|name>` — run a game directly (index is zero-based)
- `clia reset [<index|name>] [-y]` — delete highscores for a game or all games
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
