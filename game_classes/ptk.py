import os
import sys
import shutil
import threading
import queue
import time

from prompt_toolkit.input import create_input
from prompt_toolkit.keys import Keys

# basic color constants (match curses style usage)
COLOR_BLACK = 0
COLOR_RED = 1
COLOR_GREEN = 2
COLOR_YELLOW = 3
COLOR_BLUE = 4
COLOR_MAGENTA = 5
COLOR_CYAN = 6
COLOR_WHITE = 7

A_NORMAL = 0
A_BOLD = 1 << 0
A_DIM = 1 << 1
A_REVERSE = 1 << 2

KEY_LEFT = 260
KEY_RIGHT = 261
KEY_UP = 259
KEY_DOWN = 258
KEY_PPAGE = 339
KEY_NPAGE = 338
KEY_BACKSPACE = 263
KEY_ENTER = 10

_ANSI_COLORS = {
    COLOR_BLACK: 30,
    COLOR_RED: 31,
    COLOR_GREEN: 32,
    COLOR_YELLOW: 33,
    COLOR_BLUE: 34,
    COLOR_MAGENTA: 35,
    COLOR_CYAN: 36,
    COLOR_WHITE: 37,
}


def color_pair(color):
    return int(color) << 8


def curs_set(_):
    return None


def has_colors():
    return True


def start_color():
    return None


def use_default_colors():
    return None


def can_change_color():
    return False


def init_color(*_args, **_kwargs):
    return None


def init_pair(*_args, **_kwargs):
    return None


def _decode_attr(attr):
    color = (attr >> 8) & 0xFF
    bold = bool(attr & A_BOLD)
    dim = bool(attr & A_DIM)
    reverse = bool(attr & A_REVERSE)
    return color, bold, dim, reverse


class _Screen:
    def __init__(self):
        _enable_vt_mode()
        self._queue = queue.Queue()
        self._stop = threading.Event()
        self._use_msvcrt = os.name == "nt"
        self._input = None
        self._thread = None
        if not self._use_msvcrt:
            self._input = create_input()
            self._thread = threading.Thread(target=self._reader, daemon=True)
            self._thread.start()
        self._timeout = 0.0
        self._buffer = []
        self._attrs = []
        self._rows = 24
        self._cols = 80
        self._refresh_size()
        self.clear()
        try:
            sys.stdout.write("\x1b[?1049h\x1b[?25l")
            sys.stdout.flush()
        except Exception:
            pass

    def _refresh_size(self):
        try:
            size = shutil.get_terminal_size()
            self._cols = size.columns
            self._rows = size.lines
        except Exception:
            self._cols = 80
            self._rows = 24

    def _reader(self):
        if not self._input:
            return
        with self._input:
            while not self._stop.is_set():
                try:
                    for key in self._input.read_keys():
                        self._queue.put(key)
                except Exception:
                    time.sleep(0.01)

    def stop(self):
        self._stop.set()
        try:
            if self._input:
                self._input.close()
        except Exception:
            pass

    def nodelay(self, _flag=True):
        return None

    def timeout(self, ms):
        try:
            self._timeout = max(0.0, float(ms) / 1000.0)
        except Exception:
            self._timeout = 0.0

    def keypad(self, _flag=True):
        return None

    def getmaxyx(self):
        self._refresh_size()
        return self._rows, self._cols

    def clear(self):
        self._refresh_size()
        self._buffer = [[" " for _ in range(self._cols)] for _ in range(self._rows)]
        self._attrs = [[0 for _ in range(self._cols)] for _ in range(self._rows)]

    def bkgd(self, _ch, _attr=0):
        return None

    def addstr(self, y, x, text, attr=0):
        if text is None:
            return
        try:
            s = str(text)
        except Exception:
            return
        if y < 0 or y >= self._rows:
            return
        for i, ch in enumerate(s):
            px = x + i
            if 0 <= px < self._cols:
                self._buffer[y][px] = ch
                self._attrs[y][px] = attr

    def addch(self, y, x, ch, attr=0):
        if y < 0 or y >= self._rows or x < 0 or x >= self._cols:
            return
        try:
            c = chr(ch) if isinstance(ch, int) else str(ch)
        except Exception:
            return
        if not c:
            return
        self._buffer[y][x] = c[0]
        self._attrs[y][x] = attr

    def refresh(self):
        out_lines = []
        for y in range(self._rows):
            line = []
            prev_attr = None
            for x in range(self._cols):
                attr = self._attrs[y][x]
                if attr != prev_attr:
                    color, bold, dim, reverse = _decode_attr(attr)
                    seq = "\x1b[0m"
                    if bold:
                        seq += "\x1b[1m"
                    if dim:
                        seq += "\x1b[2m"
                    if reverse:
                        seq += "\x1b[7m"
                    if attr != 0 and color in _ANSI_COLORS:
                        seq += f"\x1b[{_ANSI_COLORS[color]}m"
                    line.append(seq)
                    prev_attr = attr
                line.append(self._buffer[y][x])
            line.append("\x1b[0m")
            out_lines.append("".join(line))
        sys.stdout.write("\x1b[H" + "\n".join(out_lines))
        sys.stdout.flush()

    def getch(self):
        if self._use_msvcrt:
            return _getch_msvcrt(self._timeout)
        try:
            key = self._queue.get(timeout=self._timeout)
        except Exception:
            return -1
        return _map_keypress(key)


def _map_keypress(keypress):
    key = keypress.key
    if key == Keys.Left:
        return KEY_LEFT
    if key == Keys.Right:
        return KEY_RIGHT
    if key == Keys.Up:
        return KEY_UP
    if key == Keys.Down:
        return KEY_DOWN
    if key == Keys.PageUp:
        return KEY_PPAGE
    if key == Keys.PageDown:
        return KEY_NPAGE
    if key in (Keys.Backspace, Keys.ControlH):
        return KEY_BACKSPACE
    if key in (Keys.Enter, Keys.ControlM):
        return 10
    if isinstance(key, str) and len(key) == 1:
        return ord(key)
    return -1


def _getch_msvcrt(timeout):
    try:
        import msvcrt
    except Exception:
        time.sleep(timeout)
        return -1
    end = time.time() + timeout
    while True:
        if msvcrt.kbhit():
            ch = msvcrt.getwch()
            if ch in ("\x00", "\xe0"):
                ch2 = msvcrt.getwch()
                return {
                    "K": KEY_LEFT,
                    "M": KEY_RIGHT,
                    "H": KEY_UP,
                    "P": KEY_DOWN,
                    "I": KEY_PPAGE,
                    "Q": KEY_NPAGE,
                }.get(ch2, -1)
            if ch == "\r":
                return 10
            if ch == "\x08":
                return KEY_BACKSPACE
            return ord(ch)
        if timeout <= 0:
            return -1
        if time.time() >= end:
            return -1
        time.sleep(0.01)


def _enable_vt_mode():
    if os.name != "nt":
        return
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)
        mode = ctypes.c_uint()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            kernel32.SetConsoleMode(handle, mode.value | 0x0004)
    except Exception:
        pass


def exit_alternate_screen():
    """Exit the alternate screen buffer and restore the cursor/attributes.

    Safe to call from anywhere; used when printing messages that must
    appear in the main terminal/scrollback.
    """
    try:
        sys.stdout.write("\x1b[0m\x1b[?25h\x1b[?1049l")
        sys.stdout.flush()
    except Exception:
        pass


def wrapper(func):
    stdscr = _Screen()
    try:
        return func(stdscr)
    finally:
        stdscr.stop()
        try:
            sys.stdout.write("\x1b[0m\x1b[2J\x1b[3J\x1b[H\x1b[?25h\x1b[?1049l")
            sys.stdout.flush()
        except Exception:
            pass
