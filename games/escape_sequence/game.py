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

TITLE = [                                                                                                                         
  ' ██████  ▄▄▄▄  ▄▄▄▄  ▄▄▄  ▄▄▄▄  ▄▄▄▄▄   ▄█████ ▄▄▄▄▄  ▄▄▄  ▄▄ ▄▄ ▄▄▄▄▄ ▄▄  ▄▄  ▄▄▄▄ ▄▄▄▄▄ ',
  ' ██▄▄   ███▄▄ ██▀▀▀ ██▀██ ██▄█▀ ██▄▄    ▀▀▀▄▄▄ ██▄▄  ██▀██ ██ ██ ██▄▄  ███▄██ ██▀▀▀ ██▄▄  ',
  ' ██▄▄▄▄ ▄▄██▀ ▀████ ██▀██ ██    ██▄▄▄   █████▀ ██▄▄▄ ▀███▀ ▀███▀ ██▄▄▄ ██ ▀██ ▀████ ██▄▄▄ ',
  '                                                       ▀▀                                 '
]

# minimum terminal size required to run this game (cols, rows)
MIN_COLS = 70
MIN_ROWS = 20

class Game(GameBase):
    def __init__(self, stdscr, player_name='Player'):
        self.title = TITLE
        self.highscores = HighScores('escape_sequence', {
            'score': {'player': 'Player', 'value': 0},
        })
        super().__init__(stdscr, player_name, 0.06, ptk.COLOR_CYAN)
        self.init_scores([['score', 0]])

        # simple box state (moves only on input)
        self.x = self.width // 2
        self.y = self.height // 2

    def draw_info(self):
        try:
            info_x = 2
            info_y = len(self.title)
            self.stdscr.addstr(info_y + 1, info_x, f'Player: {self.player_name}')
            self.stdscr.addstr(info_y + 2, info_x, f'Score: {int(self.scores["score"]):,}', ptk.color_pair(ptk.COLOR_GREEN))
        except Exception:
            pass

    def draw(self):
        self.draw_info()
        try:
            ch = glyph('BLOCK')
        except Exception:
            ch = '#'
        try:
            self.stdscr.addch(int(self.y), int(self.x), ch, ptk.color_pair(ptk.COLOR_YELLOW) | ptk.A_BOLD)
        except Exception:
            pass

    def step(self, now):
        # No automatic movement; ticks do nothing for this simple game.
        return

    def movement(self, ch):
        # allow arrow keys or WASD to nudge the box
        if ch in (ptk.KEY_LEFT, ord('a')):
            self.x = max(0, self.x - 2)
            self.scores['score'] += 1
        elif ch in (ptk.KEY_RIGHT, ord('d')):
            self.x = min(self.width - 1, self.x + 2)
            self.scores['score'] += 1
        elif ch in (ptk.KEY_UP, ord('w')):
            self.y = max(0, self.y - 1)
            self.scores['score'] += 1
        elif ch in (ptk.KEY_DOWN, ord('s')):
            self.y = min(self.height - 1, self.y + 1)
            self.scores['score'] += 1

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
