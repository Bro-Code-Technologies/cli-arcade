import os
import sys
import shutil
import threading
import queue
import time

_HAS_PROMPT_TOOLKIT = True
try:
    from prompt_toolkit.input import create_input
    from prompt_toolkit.keys import Keys
except Exception:
    create_input = None
    Keys = None
    _HAS_PROMPT_TOOLKIT = False
import select

_HAS_TERMIOS = True
try:
    import termios
    import tty
except Exception:
    termios = None
    tty = None
    _HAS_TERMIOS = False

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
        self._posix_fd = None
        self._orig_term_attrs = None
        if not self._use_msvcrt:
            # Prefer a simple termios-based reader on POSIX for raw key capture
            if _HAS_TERMIOS:
                try:
                    self._posix_fd = sys.stdin.fileno()
                    self._orig_term_attrs = termios.tcgetattr(self._posix_fd)
                    tty.setcbreak(self._posix_fd)
                    self._thread = threading.Thread(target=self._posix_reader, daemon=True)
                    self._thread.start()
                except Exception:
                    # fall back to prompt_toolkit if termios fails
                    self._posix_fd = None
                    self._orig_term_attrs = None
            if self._posix_fd is None and _HAS_PROMPT_TOOLKIT and create_input is not None:
                try:
                    self._input = create_input()
                    self._thread = threading.Thread(target=self._reader, daemon=True)
                    self._thread.start()
                except Exception as e:
                    self._input = None
                    sys.stderr.write(f"[ptk] create_input failed: {e}\n")
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
                except Exception as e:
                    # log and continue — don't let the thread die silently
                    sys.stderr.write(f"[ptk] reader exception: {e}\n")
                    time.sleep(0.01)

    def _posix_reader(self):
        if not _HAS_TERMIOS:
            return
        fd = self._posix_fd
        buf = b""
        while not self._stop.is_set():
            try:
                r, _, _ = select.select([fd], [], [], 0.1)
                if not r:
                    continue
                chunk = os.read(fd, 32)
                if not chunk:
                    continue
                buf += chunk
                # process buffer for known sequences
                while buf:
                    # single-byte control checks
                    if buf.startswith(b"\x1b"):
                        # escape sequences: try to consume common sequences
                        if buf.startswith(b"\x1b[A"):
                            self._queue.put(KEY_UP)
                            buf = buf[3:]
                            continue
                        if buf.startswith(b"\x1b[B"):
                            self._queue.put(KEY_DOWN)
                            buf = buf[3:]
                            continue
                        if buf.startswith(b"\x1b[C"):
                            self._queue.put(KEY_RIGHT)
                            buf = buf[3:]
                            continue
                        if buf.startswith(b"\x1b[D"):
                            self._queue.put(KEY_LEFT)
                            buf = buf[3:]
                            continue
                        # PageUp/PageDown common sequences
                        if buf.startswith(b"\x1b[5~"):
                            self._queue.put(KEY_PPAGE)
                            buf = buf[4:]
                            continue
                        if buf.startswith(b"\x1b[6~"):
                            self._queue.put(KEY_NPAGE)
                            buf = buf[4:]
                            continue
                        # unknown escape: drop single ESC
                        self._queue.put(27)
                        buf = buf[1:]
                        continue
                    # newline / carriage return
                    if buf[0] in (10, 13):
                        self._queue.put(10)
                        buf = buf[1:]
                        continue
                    # backspace (DEL or BS)
                    if buf[0] in (8, 127):
                        self._queue.put(KEY_BACKSPACE)
                        buf = buf[1:]
                        continue
                    # regular printable character
                    ch = buf[0]
                    if 32 <= ch <= 126:
                        self._queue.put(ch)
                        buf = buf[1:]
                        continue
                    # unhandled byte: drop
                    buf = buf[1:]
            except Exception as e:
                sys.stderr.write(f"[ptk] posix_reader exception: {e}\n")
                time.sleep(0.01)

    def stop(self):
        self._stop.set()
        try:
            if self._input:
                self._input.close()
        except Exception:
            pass
        # restore termios attrs if we changed them
        try:
            if self._orig_term_attrs is not None and _HAS_TERMIOS:
                termios.tcsetattr(self._posix_fd, termios.TCSANOW, self._orig_term_attrs)
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
        # key may be an int from posix reader or a keypress object from prompt_toolkit
        if isinstance(key, int):
            return key
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
