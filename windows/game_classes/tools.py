import curses
import os
import shutil

def verify_terminal_size(game_name, min_cols=70, min_rows=20):
    try:
        size = shutil.get_terminal_size()
        cols, rows = size.columns, size.lines
    except Exception:
        try:
            cols, rows = os.get_terminal_size().columns, os.get_terminal_size().lines
        except Exception:
            cols, rows = 0, 0
    if cols < min_cols or rows < min_rows:
        print(f"  [ACTION] Terminal size is too small to run {game_name}.")
        if cols < min_cols:
          print(f"  [ACTION] Actual Colums: {cols} Required Colums: {min_cols}")
        if rows < min_rows:
          print(f"  [ACTION] Actual Rows: {rows} Required Rows: {min_rows}")
        raise SystemExit(1)

def get_terminal_size(stdscr):
    try:
      rows, cols = stdscr.getmaxyx()
    except Exception:
      try:
        cols, rows = shutil.get_terminal_size()
      except Exception:
        cols, rows = 24, 80
    return max(20, cols - 2), max(6, rows - 1)

def init_curses(stdscr):
  curses.curs_set(0)
  stdscr.nodelay(True)
  stdscr.timeout(50)
  # enable keypad mode so special keys (e.g. numpad Enter) map to curses.KEY_ENTER
  try:
      stdscr.keypad(True)
  except Exception:
      pass
  # init colors
  curses.start_color()
  curses.use_default_colors()
  # try to normalize key colors (0..1000 scale). Must run before init_pair.
  if curses.can_change_color() and curses.COLORS >= 8:
      try:
          curses.init_color(curses.COLOR_MAGENTA, 1000, 0, 1000)
          curses.init_color(curses.COLOR_YELLOW, 1000, 1000, 0)
          curses.init_color(curses.COLOR_WHITE, 1000, 1000, 1000)
          curses.init_color(curses.COLOR_CYAN, 0, 1000, 1000)
          curses.init_color(curses.COLOR_BLUE, 0, 0, 1000)
          curses.init_color(curses.COLOR_GREEN, 0, 800, 0)
          curses.init_color(curses.COLOR_RED, 1000, 0, 0)
          curses.init_color(curses.COLOR_BLACK, 0, 0, 0)
      except Exception:
          pass
  for i in range(1,8):
      curses.init_pair(i, i, -1)
  # set an explicit default attribute so unstyled text uses white
  try:
      stdscr.bkgd(' ', curses.color_pair(curses.COLOR_WHITE))
  except Exception:
      try:
          stdscr.bkgd(' ', curses.color_pair(7))
      except Exception:
          pass

def clamp(v, a, b):
	return max(a, min(b, v))

def is_enter_key(ch):
    try:
        enter_vals = {10, 13, getattr(curses, 'KEY_ENTER', -1), 343, 459}
    except Exception:
        enter_vals = {10, 13}
    return ch in enter_vals


def _supports_unicode():
    """Decide whether to use Unicode glyphs.

    Rules:
    - Honor `CLI_ARCADE_FORCE_ASCII` (1/true/yes) -> False
    - On classic Windows PowerShell/conhost (no modern terminal env vars) prefer ASCII
    - If encodings are explicitly ASCII -> False
    - Otherwise prefer Unicode (True)
    """
    try:
        if os.environ.get('CLI_ARCADE_FORCE_ASCII', '').lower() in ('1', 'true', 'yes'):
            return False

        # On Windows, many older/conhost-based shells lack glyph fonts.
        # If we're on Windows and don't detect a modern terminal emulator,
        # prefer ASCII to avoid boxed question-mark glyphs.
        if os.name == 'nt':
            env = os.environ
            modern_term_markers = (
                'WT_SESSION',  # Windows Terminal
                'WT_PROFILE_ID',
                'TERM_PROGRAM',
                'ANSICON',
                'ConEmuPID',
                'TERM',
            )
            modern = any(k in env for k in modern_term_markers)
            term = env.get('TERM', '').lower()
            if 'xterm' in term or 'vt' in term:
                modern = True
            if not modern:
                return False

        import sys
        import locale
        encs = [getattr(sys.stdout, 'encoding', None), locale.getpreferredencoding(False)]
        for enc in encs:
            if not enc:
                continue
            low = enc.lower()
            if 'ascii' in low or low in ('us-ascii', '646'):
                return False

        return True
    except Exception:
        return True


_UNICODE = _supports_unicode()

GLYPHS_UNICODE = {
    'VBAR': '│',
    'BLOCK': '█',
    'CIRCLE_FILLED': '◉',
    'CIRCLE': '◌',
    'THUMB': '█',
}
GLYPHS_ASCII = {
    'VBAR': '|',
    'BLOCK': '#',
    'CIRCLE_FILLED': 'O',
    'CIRCLE': 'O',
    'THUMB': '#',
}


def glyph(name, fallback='*'):
    """Return a glyph string for `name`, using unicode when available.

    Known names: 'VBAR', 'BLOCK', 'CIRCLE_FILLED', 'CIRCLE', 'THUMB'
    """
    try:
        if _UNICODE:
            return GLYPHS_UNICODE.get(name, GLYPHS_UNICODE.get('CIRCLE_FILLED', fallback))
        return GLYPHS_ASCII.get(name, GLYPHS_ASCII.get('CIRCLE_FILLED', fallback))
    except Exception:
        return fallback