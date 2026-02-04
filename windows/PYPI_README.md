# CLI Arcade

Collection of small terminal games bundled with a single CLI launcher.

Requirements
- Python 3.8+

Quick start
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

Commands
- `clia` — interactive terminal menu
- `clia list` — print available games and zero-based indices
- `clia run <index|name>` — run a game directly (index is zero-based)
- `clia reset [<index|name>] [-y]` — delete highscores for a game or all games
- Aliases available: `cli-arcade`

License
- MIT

Changelog
- See CHANGELOG.md
