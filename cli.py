from game_classes import ptk
from game_classes.tools import verify_terminal_size
import os
import importlib.util
import argparse
import glob
import sys
import re
import time
import textwrap

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
            # try to read declared minimum terminal size from the game file
            min_cols = None
            min_rows = None
            try:
                with open(file_to_check, 'r', encoding='utf-8') as fh:
                    src = fh.read()
                # try to read DESCRIPTION from the game file (triple-quoted or single-line)
                try:
                    mdesc = re.search(r"DESCRIPTION\s*=\s*(?P<quote>\'\'\'|\"\"\")(.*?)(?P=quote)", src, re.S)
                    if mdesc:
                        desc_text = mdesc.group(2).strip()
                    else:
                        m2 = re.search(r"DESCRIPTION\s*=\s*(?P<q>['\"])(?P<t>.*?)(?P=q)", src)
                        desc_text = m2.group('t').strip() if m2 else None
                except Exception:
                    desc_text = None
                m = re.search(r'MIN_TERMINAL\s*=\s*\(\s*(\d+)\s*,\s*(\d+)\s*\)', src)
                if m:
                    min_cols = int(m.group(1))
                    min_rows = int(m.group(2))
                else:
                    m1 = re.search(r'MIN_COLS\s*=\s*(\d+)', src)
                    m2 = re.search(r'MIN_ROWS\s*=\s*(\d+)', src)
                    if m1:
                        min_cols = int(m1.group(1))
                    if m2:
                        min_rows = int(m2.group(1))
            except Exception:
                min_cols = None
                min_rows = None
            # use directory name as the display name
            name = entry.replace('_', ' ').title()
            rel = os.path.relpath(file_to_check, base).replace('\\', '/')
            games.append((name, rel))
            try:
                # store extracted description by slug (directory name)
                if desc_text:
                    GAME_DESCS[entry] = desc_text
            except Exception:
                pass
            try:
                GAME_MINS[rel] = (min_cols, min_rows)
            except Exception:
                pass
    return games


GAME_MINS = {}
# Mapping filled during discovery
GAME_DESCS = {}
GAMES = _discover_games()

# Mapping of game slug -> description extracted from the game's source file.
# Game authors can define a DESCRIPTION variable in their game module; it will
# be shown in the menu. Example in a game's `game.py`:
#    DESCRIPTION = "Short description of the game"
# Padding (spaces) between the border and content inside the right-hand panel.
# Increase to widen inner padding; default is 1.
PANEL_PADDING = 1


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

        # Reserve a right-hand panel for descriptions/highscores.
        # Right panel gets up to ~40 cols or remaining space; left list uses the rest.
        right_w = min(40, max(20, w))
        left_w = max(20, w - right_w - 6)
        for vis_i in range(min(avail, total)):
            i = top + vis_i
            name = GAMES[i][0]
            attr = ptk.A_REVERSE if i == sel else ptk.A_NORMAL
            try:
                stdscr.addstr(start_y + vis_i, 2, name[:left_w - 2], ptk.color_pair(ptk.COLOR_CYAN) | attr)
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
        # Draw right-hand panel for the currently selected game's description
        # and highscores. This is updated every frame as the selection changes.
        try:
            # determine slug (directory name) for selected game
            rel = GAMES[sel][1]
            slug = os.path.basename(os.path.dirname(rel))
            desc = GAME_DESCS.get(slug, '')

            # Position the panel 3 spaces to the right of the longest game title.
            max_name_len = max((len(n) for n, _ in GAMES), default=0)
            panel_x = 3 + max_name_len
            # If the calculated panel would overflow the screen, fall back
            # to the previous conservative position based on `left_w`.
            if panel_x + right_w + 1 > w:
                panel_x = left_w + 2
            # shift panel up one row so it sits 1 line above the list area
            panel_y = max(0, start_y - 1)
            # draw a border around the panel
            try:
                from game_classes.tools import _UNICODE as _USE_UNI
            except Exception:
                _USE_UNI = False
            if _USE_UNI:
                tl, tr, bl, br, hch, vch = '┌', '┐', '└', '┘', '─', '│'
            else:
                tl, tr, bl, br, hch, vch = '+', '+', '+', '+', '-', '|'
            # Build content (description + highscores), compute size, draw box, then render
            try:
                wrapped = textwrap.wrap(desc, width=max(10, right_w - 4)) if desc else []
            except Exception:
                wrapped = []

            # gather highscores
            try:
                from game_classes.highscores import get_saved_highscores
                results = get_saved_highscores(slug)
                scores = results[0].get('scores') if results else None
            except Exception:
                scores = None

            hs_lines = []
            if not scores:
                hs_lines = ['No saved highscores']
            else:
                entries = []
                for k, v in scores.items():
                    if isinstance(v, dict) and 'value' in v:
                        try:
                            val = float(v.get('value', 0))
                        except Exception:
                            val = 0
                        entries.append((k, v.get('player', 'Player'), val))
                    else:
                        entries.append((k, str(v), 0))
                for ent in entries[:5]:
                    key_label = ent[0].replace('_', ' ').title()
                    if isinstance(ent[2], (int, float)):
                            try:
                                disp_val = int(ent[2])
                                disp_str = f"{disp_val:,}"
                            except Exception:
                                disp_str = str(ent[2])
                            hs_lines.append(f"{key_label}: {ent[1]} - {disp_str}")
                    else:
                        hs_lines.append(f"{key_label}: {ent[1]}")

            # Compose content lines including a header
            content_lines = []
            content_lines.append('Description:')
            content_lines.extend(wrapped)
            content_lines.append('')
            content_lines.append('Leaderboard:')
            content_lines.extend(hs_lines)

            # compute display lines (tab non-header lines), content width and panel dimensions
            headers = ('Description:', 'Leaderboard:')
            display_lines = [l if l in headers else ('  ' + l) for l in content_lines]
            left_border_x = panel_x
            content_start = left_border_x + 1 + PANEL_PADDING
            content_width = max((len(l) for l in display_lines), default=0)
            right_border_x = content_start + content_width + PANEL_PADDING
            if right_border_x >= w - 1:
                right_border_x = w - 2
                content_width = max(0, right_border_x - content_start - 1)

            panel_w = right_border_x - left_border_x + 1
            panel_h = min(avail, max(6, len(content_lines) + 2))

            # draw box
            try:
                border_attr = ptk.color_pair(ptk.COLOR_MAGENTA) | ptk.A_BOLD
                stdscr.addstr(panel_y, left_border_x, tl + (hch * (panel_w - 2)) + tr, border_attr)
                for by in range(1, panel_h - 1):
                    stdscr.addstr(panel_y + by, left_border_x, vch, border_attr)
                    try:
                        stdscr.addstr(panel_y + by, right_border_x, vch, border_attr)
                    except Exception:
                        pass
                stdscr.addstr(panel_y + panel_h - 1, left_border_x, bl + (hch * (panel_w - 2)) + br, border_attr)
            except Exception:
                pass

            # render content inside box (use display_lines with tabbing)
            try:
                for idx, line in enumerate(display_lines[: panel_h - 2]):
                    try:
                        if line in headers:
                            attr = ptk.color_pair(ptk.COLOR_CYAN) | ptk.A_BOLD
                        else:
                            attr = ptk.A_NORMAL
                        stdscr.addstr(panel_y + 1 + idx, content_start, line[:content_width], attr)
                    except Exception:
                        pass
            except Exception:
                pass
        except Exception:
            # best-effort: ignore panel rendering errors
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
            # Before leaving the menu, validate the selected game's minimum
            # terminal size (if declared). If it's too small, show an
            # on-screen message and keep the menu running.
            try:
                rel = GAMES[sel][1]
                mins = GAME_MINS.get(rel)
                if mins:
                    min_cols, min_rows = mins
                    if min_cols and min_rows and (w < int(min_cols) or h < int(min_rows)):
                        try:
                            msg = f"Terminal too small: {w}x{h}, need {min_cols}x{min_rows}. Resize to start."
                            stdscr.addstr(max(0, h-1), 2, msg[:max(0, w-4)], ptk.color_pair(ptk.COLOR_RED))
                            stdscr.refresh()
                            time.sleep(1.5)
                        except Exception:
                            pass
                        continue
            except Exception:
                pass
            return sel
        elif ch == 27:
            return None
        # adjust top to keep the selected item visible
        if sel < top:
            top = sel
        elif sel >= top + avail:
            top = sel - avail + 1


def _run_game_by_index(choice, from_menu=False):
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
            # If launched via `clia run`, exit the process after the game ends.
            if not from_menu:
                try:
                    sys.exit(0)
                except SystemExit:
                    raise
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
        'Commands:',
        f'  %(prog)s [-h|--help] [-v|--version]',
        f'  %(prog)s list [-h]',
        f'  %(prog)s run [-h] <index|name>',
        f'  %(prog)s reset [-h] [<index|name>] [-y|--yes]',
        f'  %(prog)s scores [-h] [<index|name>] [-r|--raw]',
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
    # Add scores command
    scoresp = sub.add_parser(
        'scores',
        help='Show highscores for games',
        description='Print highscores for all games or a specific game. Optionally output raw JSON.',
        epilog='Examples:\n  %(prog)s scores\n  %(prog)s scores 0\n  %(prog)s scores "Byte Bouncer"\n  %(prog)s scores -r\n',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    scoresp.add_argument('game', nargs='?', help='Optional game name or zero-based index')
    scoresp.add_argument('-r', '--raw', action='store_true', help='Output raw JSON string')

    # Hidden commands for devs
    syncp = sub.add_parser('sync')
    syncp.add_argument('scores')
    newp = sub.add_parser('new')
    newp.add_argument('name')

    args, _rest = parser.parse_known_args()

    # Hidden dev commands
    if args.cmd == 'sync':
        import json
        from game_classes.highscores import merge_update_highscores
        scores_str = getattr(args, 'scores', None)
        if not scores_str:
            print('No scores string provided.')
            return
        try:
            # Use json.loads for safe parsing
            scores_obj = json.loads(scores_str)
        except Exception as e:
            print(f'Failed to parse scores string: {e}')
            return
        updated = merge_update_highscores(scores_obj)
        print(f'Synced games: {updated}')
        return
    if args.cmd == 'new':
        # Create a new game by copying the game_template directory
        name = getattr(args, 'name', None)
        if not name:
            print('  [ERROR] No name provided for new game.')
            return
        slug = re.sub(r'[^a-z0-9]+', '_', name.lower()).strip('_')
        if not slug:
            print(f'  [ERROR] Invalid game name: {name}')
            return
        base = os.path.dirname(__file__)
        games_dir = os.path.join(base, 'games')
        target = os.path.join(games_dir, slug)
        if os.path.exists(target):
            print(f"  [ERROR] Target already exists: {target}")
            return

        template_dir = os.path.join(base, 'game_classes', 'game_template')
        if not os.path.isdir(template_dir):
            print(f"  [ERROR] Template dir not found: {template_dir}")
            return

        try:
            os.makedirs(target, exist_ok=True)
            # copy and replace placeholders in files
            for namef in sorted(os.listdir(template_dir)):
                src = os.path.join(template_dir, namef)
                dst = os.path.join(target, namef)
                # only handle regular files
                if not os.path.isfile(src):
                    continue
                try:
                    with open(src, 'r', encoding='utf-8') as fh:
                        data = fh.read()
                except Exception:
                    data = None
                if data is None:
                    # fallback to binary copy
                    try:
                        import shutil
                        shutil.copy2(src, dst)
                    except Exception as e:
                        print(f"  [WARN] Failed to copy {src}: {e}")
                    continue
                # replace placeholder token NEW_GAME with slug and a display title
                new_data = data.replace('NEW_GAME', slug)
                new_data = new_data.replace("'  NEW_GAME  '", f"'  {name}  '")
                try:
                    with open(dst, 'w', encoding='utf-8') as fh:
                        fh.write(new_data)
                except Exception as e:
                    print(f"  [WARN] Failed to write {dst}: {e}")
            print(f"  [CREATED] Game scaffold at: {target}")
            print(f"  [INFO] Use 'clia list' to see the new game and 'clia run \"{name}\"' to run it.")
        except Exception as e:
            print(f"  [ERROR] Failed to create game: {e}")
        return

    # Public commands
    if args.cmd == 'scores':
        import json
        base = os.path.dirname(__file__)
        games = GAMES
        token = getattr(args, 'game', None)
        raw = getattr(args, 'raw', False)
        selected_dir = None
        selected_display = None
        if token is not None:
            # Try integer index
            try:
                idx = int(token)
                if 0 <= idx < len(games):
                    # store both display name and directory name
                    selected_display, rel = games[idx]
                    selected_dir = os.path.basename(os.path.dirname(rel))
                else:
                    print(f"  [INFO] Index out of range: {idx}")
                    for i, (name, rel) in enumerate(games):
                        print(f"    [{i}] {name}")
                    return
            except Exception:
                # Match by exact name (case-insensitive)
                lowered = token.lower()
                for i, (name, rel) in enumerate(games):
                    if name.lower() == lowered:
                        selected_display = name
                        selected_dir = os.path.basename(os.path.dirname(rel))
                        break
                # Substring match
                if selected_dir is None:
                    for i, (name, rel) in enumerate(games):
                        if lowered in name.lower():
                            selected_display = name
                            selected_dir = os.path.basename(os.path.dirname(rel))
                            break
                if selected_dir is None:
                    print(f"  [INFO] Game not found: {token}")
                    for i, (name, rel) in enumerate(games):
                        print(f"    [{i}] {name}")
                    return
        def pretty_print_scores(game, scores, tab=''):
            # Convert snake_case dir names (e.g. byte_bouncer_2) to Title Case
            print(f"{tab}{game.replace('_', ' ').title()}")
            if not scores:
                print("  [INFO] No saved highscores")
                return
            for key, value in scores.items():
                if isinstance(value, dict) and 'player' in value and 'value' in value:
                    player = value.get('player', 'Unknown')
                    val = value.get('value', 0)
                    try:
                        if isinstance(val, float) or (isinstance(val, str) and '.' in str(val)):
                            val_disp = int(float(val))
                        else:
                            val_disp = int(val)
                        val_str = f"{val_disp:,}"
                    except Exception:
                        val_str = str(val)
                    print(f"{tab}  {key}: {player} - {val_str}")
                else:
                    print(f"{tab}  {key}: {value}")

        from game_classes.highscores import get_saved_highscores

        if selected_dir:
            disp = selected_display or selected_dir
            results = get_saved_highscores(selected_dir)
            if not results:
                print(f"  [INFO] No saved highscores for: {disp}")
                return
            scores = results[0]['scores']
            if raw:
                out = json.dumps(scores)
                print(out.replace('"', '\\"'))
            else:
                pretty_print_scores(disp, scores)
        else:
            results = get_saved_highscores()
            if raw:
                mapping = {r['game']: r['scores'] for r in results}
                out = json.dumps(mapping)
                print(out.replace('"', '\\"'))
            else:
                print("Leaderboard")
                for r in results:
                    pretty_print_scores(r['game'], r['scores'], '  ')
        return

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
            _run_game_by_index(choice, from_menu=False)
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

    # Interactive menu loop: verify terminal size before showing menu each time,
    # run the selected game, then return to the menu when the game exits.
    while True:
        try:
            verify_terminal_size('CLI Arcade', 70, 25)
        except SystemExit:
            return
        choice = ptk.wrapper(_menu)
        if choice is None:
            break
        # Run the selected game (this returns when the game exits, e.g. ESC)
        try:
            _run_game_by_index(choice, from_menu=True)
        except Exception as e:
            print(f"  [ERROR] Error running game: {e}")


if __name__ == '__main__':
    main()
