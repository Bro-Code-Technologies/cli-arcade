from game_classes import ptk
import os
import sys

try:
  this_dir = os.path.dirname(__file__)
  project_root = os.path.abspath(os.path.join(this_dir, '..', '..'))
  if project_root not in sys.path:
    sys.path.insert(0, project_root)
except Exception:
  project_root = None

from game_classes.highscores import HighScores
from game_classes.game_base import GameBase
from game_classes.menu import Menu
from game_classes.tools import init_ptk, glyph
import json

TITLE = [
  ' ______                          _     _   _                              ',
 r' | ___ \                        | |   | | | |                             ',
  ' | |_/ / __ ___  _ __ ___  _ __ | |_  | |_| | ___  _ __  _ __   ___ _ __  ',
 r" |  __/ '__/ _ \| '_ ` _ \| '_ \| __| |  _  |/ _ \| '_ \| '_ \ / _ \ '__| ",
  ' | |  | | | (_) | | | | | | |_) | |_  | | | | (_) | |_) | |_) |  __/ |    ',
 r' \_|  |_|  \___/|_| |_| |_| .__/ \__| \_| |_/\___/| .__/| .__/ \___|_|    ',
  '                          | |                     | |   | |               ',
  '                          |_|                     |_|   |_|               ',
]

DESCRIPTION = """Put something here!
This is a template for building new games.
You can customize the title, description, and game logic to create your own unique game.
The description will be shown in the menu, so make it enticing!"""

# minimum terminal size required to run this game (cols, rows)
MIN_COLS = 100
MIN_ROWS = 30

class Game(GameBase):
    def __init__(self, stdscr, player_name='Player'):
        self.title = TITLE
        self.highscores = HighScores('prompt_hopper', {
            'score': {'player': 'Player', 'value': 0},
            'stars': {'player': 'Player', 'value': 0},
            'level': {'player': 'Player', 'value': 0},
        })
        super().__init__(stdscr, player_name, 0.03, ptk.COLOR_MAGENTA)
        self.init_scores([['score', 0]])
        # start level and text-only map
        self.level = 0
        self.texts = []
        self.ground_text_lines = []
        self.ground_y = None
        self.x_offset = 0
        self.y_offset = 0
        self.player_x = None
        self.player_y = None
        # map vertical physics (map moves up to simulate player falling)
        self.map_y_offset_f = 0.0
        self.map_v = -0.2
        self.map_gravity = 0.02
        self.map_v_max = -1.5
        self.load_level(self.level)
        # player fixed position: centered X and 5 rows up from bottom
        try:
            self.player_x = max(0, self.width // 2)
            self.player_y = max(0, self.height - 5)
        except Exception:
            self.player_x = 0
            self.player_y = max(0, 0)

    def draw_info(self):
        try:
            info_x = 2
            info_y = len(self.title) - 2
            # overlay info at top so map uses whole screen
            self.stdscr.addstr(info_y + 1, info_x, f'Score: {int(self.scores["score"]):,}', ptk.color_pair(ptk.COLOR_GREEN))
            self.stdscr.addstr(info_y + 2, info_x, f'Level: {int(self.scores["score"])}', ptk.color_pair(ptk.COLOR_GREEN))
            self.stdscr.addstr(info_y + 3, info_x, f'Player: {self.player_name}')
        except Exception:
            pass

    def draw(self):
        # overlay info
        self.draw_info()
        # draw only the mapped text from the level (no platform glyphs)
        try:
            # use configured magenta pair for prompt/ground styling
            try:
                prompt_attr = ptk.color_pair(ptk.COLOR_MAGENTA) | ptk.A_BOLD #| ptk.A_REVERSE
            except Exception:
                try:
                    prompt_attr = ptk.A_BOLD | ptk.A_REVERSE
                except Exception:
                    prompt_attr = ptk.A_BOLD

            map_y_off_int = int(getattr(self, 'map_y_offset_f', 0))
            for t in self.texts:
                try:
                    x = int(t.get('x', 0))
                    y = int(t.get('y', 0))
                    sx = x + int(getattr(self, 'x_offset', 0))
                    sy = y + map_y_off_int
                    s = str(t.get('text', ''))
                    if sy < 0 or sx >= self.width or sy >= self.height:
                        continue
                    # truncate to width
                    s = s[:max(0, self.width - sx)]
                    if not s:
                        continue
                    # use prompt styling for prompt- or ground-kind, otherwise default
                    if t.get('kind') in ('prompt', 'ground'):
                        try:
                            self.stdscr.addstr(sy, sx, s, prompt_attr)
                        except Exception:
                            try:
                                self.stdscr.addstr(sy, sx, s)
                            except Exception:
                                pass
                    else:
                        try:
                            self.stdscr.addstr(sy, sx, s)
                        except Exception:
                            pass
                except Exception:
                    pass
            # (ground segments are now added to self.texts as kind='ground')

            # draw player glyph at the centered player position
            try:
                if getattr(self, 'player_x', None) is not None and getattr(self, 'player_y', None) is not None:
                    px = int(self.player_x)
                    py = int(self.player_y)
                    if 0 <= py < self.height and 0 <= px < self.width:
                        try:
                            self.stdscr.addstr(py, px, 'o', ptk.color_pair(ptk.COLOR_WHITE) | ptk.A_BOLD)
                        except Exception:
                            try:
                                self.stdscr.addstr(py, px, 'o')
                            except Exception:
                                pass
            except Exception:
                pass
        except Exception:
            pass

    def load_level(self, level=0):
        # load JSON level file and populate only textual elements at mapped positions
        data = {}
        try:
            lvl_path = os.path.join(os.path.dirname(__file__), 'levels', f'{level}.json')
            with open(lvl_path, 'r', encoding='utf-8') as fh:
                data = json.load(fh)
        except Exception:
            data = {}

        # compute ground line 3 rows above bottom
        try:
            self.ground_y = max(0, self.height - 3)
        except Exception:
            self.ground_y = None

        self.texts = []

        # parse ground array: treat strings as platform segments and ints as gaps
        # ints represent horizontal breaks and should not be included in the text
        x_cursor = 0
        for entry in data.get('ground', []):
            if isinstance(entry, str):
                seg = entry
                # add a ground-kind text at the ground y
                if self.ground_y is not None:
                    self.texts.append({'x': x_cursor, 'y': self.ground_y, 'text': seg, 'kind': 'ground'})
                x_cursor += len(seg)
            elif isinstance(entry, int):
                try:
                    x_cursor += int(entry)
                except Exception:
                    x_cursor += 1
            else:
                seg = str(entry)
                if self.ground_y is not None:
                    self.texts.append({'x': x_cursor, 'y': self.ground_y, 'text': seg, 'kind': 'ground'})
                x_cursor += len(seg)

        # parse platforms: position = [x, up]
        for p in data.get('platforms', []):
            pos = p.get('position', [0, 0])
            try:
                px = int(pos[0])
            except Exception:
                px = 0
            try:
                up = int(pos[1]) if len(pos) > 1 else 0
            except Exception:
                up = 0

            # determine platform baseline y: if no prompt, platform sits on ground
            has_prompt = bool(p.get('prompt'))
            if has_prompt:
                py = (self.ground_y - up) if self.ground_y is not None else 0
            else:
                py = self.ground_y if self.ground_y is not None else 0

            # prompt is treated as text at the platform position
            if 'prompt' in p and p.get('prompt') is not None:
                self.texts.append({'x': px, 'y': py, 'text': str(p.get('prompt')), 'kind': 'prompt'})

            # skip area_* items for now (user requested)

        # handle start: center the start x on screen and apply vertical offset (downwards)
        # default offsets
        self.x_offset = getattr(self, 'x_offset', 0)
        self.y_offset = getattr(self, 'y_offset', 0)
        self.player_x = None
        self.player_y = None
        if 'start' in data:
            try:
                st = data.get('start', [0])
                sx = int(st[0]) if len(st) > 0 else 0
            except Exception:
                sx = 0
            try:
                dy = int(st[1]) if len(st) > 1 else 0
            except Exception:
                dy = 0
            # compute horizontal centering
            try:
                center_x = max(0, self.width // 2)
            except Exception:
                center_x = 0
            self.x_offset = center_x - sx
            # apply vertical offset downward from ground (texts only)
            try:
                self.y_offset = dy
            except Exception:
                self.y_offset = 0

        # apply vertical offset to every text entry
        if self.y_offset:
            for t in self.texts:
                try:
                    t['y'] = int(t.get('y', 0)) + int(self.y_offset)
                except Exception:
                    pass

        # Note: do not draw exit or glyphs — user requested text only

    def step(self, now):
        pass

    def movement(self, ch):
        # left/right movement and jump
        try:
            delta = 2
            # pressing left or 'a' should move the map right (increase x_offset)
            if ch in (ptk.KEY_LEFT, ord('a')):
                self.x_offset = int(getattr(self, 'x_offset', 0)) + delta
            # pressing right or 'd' should move the map left (decrease x_offset)
            elif ch in (ptk.KEY_RIGHT, ord('d')):
                self.x_offset = int(getattr(self, 'x_offset', 0)) - delta
            elif ch in (ptk.KEY_UP, ord('w'), ord(' ')):
                # jump (not implemented yet)
                pass
        except Exception:
            pass


def main(stdscr):
  init_ptk(stdscr)
  while True:
    game = Game(stdscr)
    menu = Menu(game)
    start = menu.display()
    if not start:
      break
    game.update_player_name(start)
    game.run()

if __name__ == '__main__':
    try:
        ptk.wrapper(main)
    except KeyboardInterrupt:
        try:
            ptk.endwin()
        except Exception:
            pass
