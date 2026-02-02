# CLI Arcade

Collection of small terminal games bundled with a single CLI launcher.

Requirements
- Python 3.8+
- On Windows: install `windows-curses` for curses support:

```powershell
pip install windows-curses
```

Quick start (developer)

```powershell
# install editable (recommended during development)
pip install -e .

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

If the `clia` command is not found after installation, the installer likely wrote scripts to your user Scripts directory. On Windows add this to your PATH (PowerShell):

```powershell
$env:Path += ";$env:APPDATA\Python\Python<version>\Scripts"
# or permanently via System settings: add %APPDATA%\Python\Python<version>\Scripts to your user PATH
```

You can always run the CLI directly without installing:

```powershell
python -m cli
```

Commands
- `clia` — interactive curses menu
- `clia list` — print available games and zero-based indices
- `clia run <index|name>` — run a game directly (index is zero-based)
- `clia reset [<index|name>] [-y]` — delete highscores for a game or all games
- Aliases available: `cli-arcade`

Highscores storage and migration
- Highscores are now stored in a user-writable application data directory. Typical locations:
	- Windows (appdirs): `%LOCALAPPDATA%\cli-arcade\games\<game>\highscores.json`
	- Fallback (no appdirs): `%USERPROFILE%\.cli-arcade\games\<game>\highscores.json`
- On first run the CLI attempts to migrate any legacy `games/<game>/highscores.json` found in the project into the user data directory.

Packaging & publishing (brief)

- `setup.cfg` now declares `packages = find:` and `include_package_data = true` so `game_classes/` and `games/` are included in sdist/wheels. Remember to add a `MANIFEST.in` if you need additional files in source distributions.
- Update `setup.cfg` version.
- Build: `py -m build` (requires `build` package).
- Upload: `twine upload dist/*` (requires `twine`).
- The package exposes several console script aliases (see `setup.cfg` -> `options.entry_points.console_scripts`).

Notes & Troubleshooting
- On Windows, `curses` requires `windows-curses`.
- The CLI requires a minimum terminal size; if the menu exits with an error, try enlarging your terminal or run `python -m cli` in a larger window.
- Games should live in their own subdirectory (`games/<slug>/game.py`) and export a `main(stdscr)` entry point. The CLI uses the directory name (slug) as the display title.

Terminal recommendations (Windows)
- Recommended: use Windows Terminal or the VS Code integrated terminal for the best UTF-8 + glyph support.
	- Install Windows Terminal via Microsoft Store or `winget`:

```powershell
winget install --id Microsoft.WindowsTerminal -e
```

- PowerShell (external) often uses OEM code page 437 and may not render some Unicode glyphs. If you prefer the external shell to render glyphs, either use Windows Terminal or make these changes:
	- Change the console font to a glyph-capable font (Cascadia Code PL, Fira Code, DejaVu Sans Mono, or modern Consolas) via the console Properties → Font.
	- Ensure UTF-8 is enabled for the session (temporary):

```powershell
chcp 65001
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = 'utf-8'
```

	- To make the change persistent, add the above lines to your PowerShell profile (see `code $profile`), or prefer PowerShell Core (`pwsh`) which typically handles UTF-8 better.

- If you cannot enable UTF-8 in your external terminal, the CLI will automatically fall back to safe ASCII glyphs for problematic terminals. To force ASCII output regardless of terminal detection, set the environment variable `CLI_ARCADE_FORCE_ASCII=1` before running the CLI.

- Advanced: enable system-wide UTF-8 (Region → Administrative → Change system locale → check “Beta: Use Unicode UTF-8 for worldwide language support”) and restart. This affects other apps and requires caution.

Contributing
- Add a new game by creating a subdirectory under `games/` with a `game.py` file that exports `main(stdscr)`.
- Keep changes minimal and run `clia` locally to verify.

License
- MIT

Changelog
- See CHANGELOG.md
