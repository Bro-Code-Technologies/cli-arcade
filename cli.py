from game_classes import ptk
from game_classes.tools import verify_terminal_size
import os
import importlib.util
import argparse
import glob
import sys

# helper: recognize Enter from multiple terminals/keypads
def is_enter_key(ch):
    try:
        enter_vals = {10, 13, getattr(ptk, 'KEY_ENTER', -1), 343, 459}
    except Exception:
        enter_vals = {10, 13}
    return ch in enter_vals

TITLE = [
   '     ________    ____   ___    ____  _________    ____  ______ ',
  r'    / ____/ /   /  _/  /   |  / __ \/ ____/   |  / __ \/ ____/ ',
  r'   / /   / /    / /   / /| | / /_/ / /   / /| | / / / / __/    ',
  r'  / /___/ /____/ /   / ___ |/ _, _/ /___/ ___ |/ /_/ / /___    ',
  r'  \____/_____/___/  /_/  |_/_/ |_|\____/_/  |_/_____/_____/    '
]

def _discover_games():
    base = os.path.dirname(__file__)
    games = []
    # only scan the 'games' subdirectory
    games_dir = os.path.join(base, 'games')
    if not os.path.isdir(games_dir):
        return []
    scan_roots = [games_dir]

    for root in scan_roots:
        for entry in sorted(os.listdir(root)):
            dirpath = os.path.join(root, entry)
            if not os.path.isdir(dirpath):
                continue
            if entry.startswith('__'):
                continue
            # prefer standardized <dir>/game.py
            candidate = os.path.join(dirpath, "game.py")
            file_to_check = None
            if os.path.exists(candidate):
                file_to_check = candidate
            else:
                pyfiles = [p for p in os.listdir(dirpath) if p.endswith('.py') and not p.startswith('_')]
                if pyfiles:
                    file_to_check = os.path.join(dirpath, pyfiles[0])
            if not file_to_check:
                continue
            # use directory name as the display name
            name = entry.replace('_', ' ').title()
            rel = os.path.relpath(file_to_check, base).replace('\\', '/')
            games.append((name, rel))
    return games


GAMES = _discover_games()


def _read_console_aliases():
    """Read console_scripts names from installed package metadata."""
    try:
        from importlib import metadata as importlib_metadata
    except Exception:
        return []

    try:
        dist = importlib_metadata.distribution('cli-arcade')
        aliases = [ep.name for ep in dist.entry_points if ep.group == 'console_scripts']
        return sorted(set(aliases))
    except Exception:
        return []


def _menu(stdscr):
    ptk.curs_set(0)
    stdscr.nodelay(False)
    # ensure a cyan color pair is available for the title
    if ptk.has_colors():
        try:
          # init colors
          ptk.start_color()
          ptk.use_default_colors()
          # try to normalize key colors (0..1000 scale). Must run before init_pair.
          if ptk.can_change_color() and ptk.COLORS >= 8:
              try:
                  ptk.init_color(ptk.COLOR_MAGENTA, 1000, 0, 1000)
                  ptk.init_color(ptk.COLOR_YELLOW, 1000, 1000, 0)
                  ptk.init_color(ptk.COLOR_WHITE, 1000, 1000, 1000)
                  ptk.init_color(ptk.COLOR_CYAN, 0, 1000, 1000)
                  ptk.init_color(ptk.COLOR_BLUE, 0, 0, 1000)
                  ptk.init_color(ptk.COLOR_GREEN, 0, 800, 0)
                  ptk.init_color(ptk.COLOR_RED, 1000, 0, 0)
                  ptk.init_color(ptk.COLOR_BLACK, 0, 0, 0)
              except Exception:
                  pass
          for i in range(1,8):
              ptk.init_pair(i, i, -1)
        except Exception:
            pass
    sel = 0
    top = 0
    while True:
        stdscr.clear()
        h, w = stdscr.getmaxyx()
        title_h = len(TITLE)
        title_start = 0
        colors = [ptk.COLOR_MAGENTA, ptk.COLOR_MAGENTA, ptk.COLOR_CYAN, ptk.COLOR_CYAN, ptk.COLOR_GREEN, ptk.COLOR_GREEN]
        for i, line in enumerate(TITLE):
            try:
                stdscr.addstr(title_start + i, 0, line, ptk.color_pair(colors[i]))
            except Exception:
                pass
        stdscr.addstr(title_h + 1, 2, "Use Up/Down, PageUp/PageDown, Enter to start, ESC to quit", ptk.color_pair(ptk.COLOR_WHITE))
        start_y = title_h + 3
        # number of lines available for the game list
        avail = max(1, h - start_y - 2)
        total = len(GAMES)
        # clamp top so it stays within valid range
        if top < 0:
            top = 0
        if top > max(0, total - avail):
            top = max(0, total - avail)

        for vis_i in range(min(avail, total)):
            i = top + vis_i
            name = GAMES[i][0]
            attr = ptk.A_REVERSE if i == sel else ptk.A_NORMAL
            try:
                stdscr.addstr(start_y + vis_i, 2, name[:w-4], ptk.color_pair(ptk.COLOR_CYAN) | attr)
            except Exception:
                pass
        # optional scrollbar indicator when list is long
        if total > avail:
            try:
                # try to use glyphs from game_classes.tools when available
                try:
                    from game_classes.tools import glyph
                    vbar = glyph('VBAR')
                    block = glyph('THUMB')
                except Exception:
                    vbar = '|' 
                    block = '#'
                bar_y = start_y
                bar_h = avail
                thumb_h = max(1, int(bar_h * (avail / total)))
                thumb_pos = int((bar_h - thumb_h) * (top / max(1, total - avail)))
                for by in range(bar_h):
                    stdscr.addstr(bar_y + by, w - 2, vbar)
                for by in range(thumb_h):
                    stdscr.addstr(bar_y + thumb_pos + by, w - 2, block)
            except Exception:
                pass
        stdscr.refresh()

        ch = stdscr.getch()
        if ch == ptk.KEY_UP:
            sel = max(0, sel - 1)
        elif ch == ptk.KEY_DOWN:
            sel = min(len(GAMES) - 1, sel + 1)
        elif ch == ptk.KEY_PPAGE:  # Page Up
            sel = max(0, sel - avail)
        elif ch == ptk.KEY_NPAGE:  # Page Down
            sel = min(len(GAMES) - 1, sel + avail)
        elif is_enter_key(ch):
            return sel
        elif ch == 27:
            return None
        # adjust top to keep the selected item visible
        if sel < top:
            top = sel
        elif sel >= top + avail:
            top = sel - avail + 1


def _run_game_by_index(choice):
    """Load and run the game given by numeric index in GAMES."""
    name, relpath = GAMES[choice]
    base = os.path.dirname(__file__)
    path = os.path.join(base, relpath)
    if not os.path.exists(path):
        print(f"  [INFO] Game file not found: {path}")
        return
    game_dir = os.path.dirname(path)
    spec = importlib.util.spec_from_file_location(f"cli_game_{choice}", path)
    mod = importlib.util.module_from_spec(spec)
    inserted = []
    try:
        # ensure both the game's directory and project root are on sys.path
        proj_root = os.path.dirname(__file__)
        if game_dir and game_dir not in sys.path:
            sys.path.insert(0, game_dir)
            inserted.append(game_dir)
        if proj_root and proj_root not in sys.path:
            sys.path.insert(0, proj_root)
            inserted.append(proj_root)
        spec.loader.exec_module(mod)
    except Exception as e:
        print(f"  [ERROR] Failed to load game {name}: {e}")
        return
    finally:
        for p in inserted:
            try:
                sys.path.remove(p)
            except Exception:
                pass
    if hasattr(mod, 'main'):
        try:
            # If the module exposes minimum terminal requirements, verify
            # them before entering the alternate screen so messages are visible
            try:
                min_cols = getattr(mod, 'MIN_COLS', None)
                min_rows = getattr(mod, 'MIN_ROWS', None)
                if min_cols is None and hasattr(mod, 'MIN_TERMINAL'):
                    t = getattr(mod, 'MIN_TERMINAL')
                    if isinstance(t, (tuple, list)) and len(t) >= 2:
                        min_cols, min_rows = t[0], t[1]
                if min_cols is not None and min_rows is not None:
                    verify_terminal_size(name, int(min_cols), int(min_rows))
            except SystemExit:
                return
            except Exception:
                pass

            ptk.wrapper(mod.main)
        except Exception as e:
            print(f"  [ERROR] Error running game {name}: {e}")
    else:
        print(f"  [INFO] Game {name} has no main(stdscr) entry point.")


def _reset_game_by_index(choice, yes=False):
    name, relpath = GAMES[choice]
    base = os.path.dirname(__file__)
    game_dir = os.path.dirname(os.path.join(base, relpath))
    # find highscores files (common pattern in project) and user-data highscores
    files = glob.glob(os.path.join(game_dir, 'highscores*.json'))
    # try user-data location via HighScores
    try:
        from game_classes.highscores import HighScores
        slug = os.path.basename(game_dir)
        hs = HighScores(slug)
        user_path = hs._path()
        if user_path and os.path.exists(user_path):
            files.append(user_path)
    except Exception:
        # if import fails or path not available, ignore
        pass
    if not files:
        print(f"  [INFO] No highscore files found for '{name}' ({game_dir}).")
        return
    # dedupe and present
    files = sorted(set(files))
    print(f"  [INFO] Found {len(files)} highscore file(s) for '{name}':")
    for f in files:
        print(f'    [{choice}] {f}')
    if not yes:
        ans = input(f"  [ACTION] Delete these files for '{name}'? [y/N]: ")
        if not ans.lower().startswith('y'):
            print('  [CANCELED]')
            return
    for f in files:
        try:
            os.remove(f)
            print(f"  [DELETED] {f}")
        except Exception as e:
            print(f"  [ERROR] Failed to delete {f}: {e}")


def _reset_all_games(yes=False):
    base = os.path.dirname(__file__)
    all_files = []
    for name, rel in GAMES:
        game_dir = os.path.dirname(os.path.join(base, rel))
        all_files.extend(glob.glob(os.path.join(game_dir, 'highscores*.json')))
        # include user-data highscores when present
        try:
            from game_classes.highscores import HighScores
            slug = os.path.basename(game_dir)
            hs = HighScores(slug)
            user_path = hs._path()
            if user_path and os.path.exists(user_path):
                all_files.append(user_path)
        except Exception:
            pass
    if not all_files:
        print('  [INFO] No highscore files found for any game.')
        return
    # dedupe list before showing
    all_files = sorted(set(all_files))
    print(f'  [INFO] Found {len(all_files)} highscore file(s):')
    for i, f in enumerate(all_files):
        print(f'    [{i}] {f}')
    if not yes:
        ans = input('  [ACTION] Delete all these highscore files? [y/N]: ')
        if not ans.lower().startswith('y'):
            print('  [CANCELED]')
            return
    for f in all_files:
        try:
            os.remove(f)
            print(f"  [DELETED] {f}")
        except Exception as e:
            print(f"  [ERROR] Failed to delete {f}: {e}")

# CLI version: read from setup.cfg to keep a single source of truth
def _read_version_from_setupcfg():
    try:
        from importlib import metadata as importlib_metadata
    except Exception:
        return '0.0.0'

    try:
        return importlib_metadata.version('cli-arcade')
    except Exception:
        return '0.0.0'

def main():
    # support simple CLI subcommands (e.g. `clia list`)
    # build epilog with examples and any console script aliases from setup.cfg
    epilog_lines = [
        'Examples:',
        f'  %(prog)s',
        f'  %(prog)s list [-h]',
        f'  %(prog)s run [-h] [0, "Byte Bouncer"]',
        f'  %(prog)s reset [-h] [0, "Byte Bouncer"] [-y]',
    ]
    aliases = _read_console_aliases()
    if aliases:
        epilog_lines.append('\nAliases: ' + ', '.join(aliases))
    epilog = '\n'.join(epilog_lines) + '\n'

    parser = argparse.ArgumentParser(
        prog=os.path.basename(sys.argv[0]) or 'games',
        description='Run the CLI Arcade menu or subcommands.',
        epilog=epilog,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    # standard --version support
    parser.add_argument('-v', '--version', action='version', version=f"%(prog)s {_read_version_from_setupcfg()}")
    sub = parser.add_subparsers(dest='cmd')
    sub.add_parser(
        'list',
        help='List available games',
        description='List all available games with their zero-based indices.',
        epilog='Example:\n  %(prog)s\n',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    runp = sub.add_parser(
        'run',
        help='Run a game by name or zero-based index',
        description='Run a game directly without the menu.',
        epilog='Examples:\n  %(prog)s 0\n  %(prog)s "Byte Bouncer"\n',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    runp.add_argument('game', help='Game name or zero-based index')
    resetp = sub.add_parser(
        'reset',
        help='Reset highscores (delete highscore files)',
        description='Delete highscores for one game or all games. Use with care.',
        epilog='Examples:\n  %(prog)s\n  %(prog)s -y\n  %(prog)s 0\n  %(prog)s "Byte Bouncer" -y\n',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    resetp.add_argument('game', nargs='?', help='Optional game name or zero-based index (omit to reset all)')
    resetp.add_argument('-y', '--yes', action='store_true', help='Do not prompt; proceed with deletion')
    args, _rest = parser.parse_known_args()

    if args.cmd == 'list':
        base = os.path.dirname(__file__)
        for i, (name, rel) in enumerate(GAMES):
            print(f"  [{i}] {name}")
        return

    if args.cmd == 'run':
        token = args.game
        choice = None
        # try integer (zero-based index)
        try:
            idx = int(token)
            if 0 <= idx < len(GAMES):
                choice = idx
            else:
                print(f"  [INFO] Index out of range: {idx}")
                for i, (name, rel) in enumerate(GAMES):
                    print(f"    [{i}] {name}")
                return
        except Exception:
            # match by exact name (case-insensitive)
            lowered = token.lower()
            for i, (name, _) in enumerate(GAMES):
                if name.lower() == lowered:
                    choice = i
                    break
            # fallback: substring match
            if choice is None:
                for i, (name, _) in enumerate(GAMES):
                    if lowered in name.lower():
                        choice = i
                        break
            if choice is None:
                print(f"  [INFO] Game not found: {token}")
                for i, (name, rel) in enumerate(GAMES):
                    print(f"    [{i}] {name}")
                return
        # run the selected game (skip menu)
        try:
            _run_game_by_index(choice)
        except Exception as e:
            print(f"  [ERROR] Error running game: {e}")
        return

    if args.cmd == 'reset':
        token = args.game
        yes = getattr(args, 'yes', False)
        if token is None:
            _reset_all_games(yes=yes)
            return
        # resolve token to index similar to 'run'
        choice = None
        try:
            idx = int(token)
            if 0 <= idx < len(GAMES):
                choice = idx
            else:
                print(f"  [INFO] Index out of range: {idx}")
                return
        except Exception:
            lowered = token.lower()
            for i, (name, _) in enumerate(GAMES):
                if name.lower() == lowered:
                    choice = i
                    break
            if choice is None:
                print(f"  [INFO] Game not found: {token}")
                return
        _reset_game_by_index(choice, yes=yes)
        return

    try:
        verify_terminal_size('CLI Arcade', 70, 20)
    except SystemExit:
        return
    # run the menu under ptk, then launch the chosen game's main()
    choice = ptk.wrapper(_menu)
    if choice is None:
        return
    name, relpath = GAMES[choice]
    base = os.path.dirname(__file__)
    path = os.path.join(base, relpath)
    if not os.path.exists(path):
        print(f"  [INFO] Game file not found: {path}")
        return
    # Ensure the game's directory is on sys.path so local imports (like `highscores`) resolve
    game_dir = os.path.dirname(path)
    spec = importlib.util.spec_from_file_location(f"cli_game_{choice}", path)
    mod = importlib.util.module_from_spec(spec)
    inserted = []
    try:
        proj_root = os.path.dirname(__file__)
        if game_dir and game_dir not in sys.path:
            sys.path.insert(0, game_dir)
            inserted.append(game_dir)
        if proj_root and proj_root not in sys.path:
            sys.path.insert(0, proj_root)
            inserted.append(proj_root)
        spec.loader.exec_module(mod)
    except Exception as e:
        print(f"  [INFO] Failed to load game {name}: {e}")
        return
    finally:
        for p in inserted:
            try:
                sys.path.remove(p)
            except Exception:
                pass
    # call the game's main function if present
    if hasattr(mod, 'main'):
        try:
            ptk.wrapper(mod.main)
        except Exception as e:
            print(f"  [ERROR] Error running game {name}: {e}")
    else:
        print(f"  [INFO] Game {name} has no main(stdscr) entry point.")


if __name__ == '__main__':
    main()
