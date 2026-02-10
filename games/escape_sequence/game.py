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
import random
import time

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
            'level': {'player': 'Player', 'value': 1},
        })
        # start with a moderate tick; will speed up as level increases
        super().__init__(stdscr, player_name, 0.12, ptk.COLOR_CYAN)
        self.init_scores([['score', 0], ['level', 1]])

        # player placement: player remains at fixed X; screen scrolls left
        self.player_x = max(6, int(self.width * 0.15))
        self.player_y = self.height // 2

        # running animation frames (simple multi-line glyphs)
        self.player_frames = [
            [ r'  O  ', r' /|\ ', r' / \ ' ],
            [ r'  O  ', r' /|\ ', r' /|  ' ],
        ]
        self.frame_index = 0
        self.frame_time = 0.0

        # obstacles: list of dicts {x, y, w, h, passed}
        self.obstacles = []
        self.spawn_acc = 0.0
        self.spawn_rate = 0.12  # base chance per tick to spawn
        self.last_step = time.time()

    def draw_info(self):
        try:
            info_x = 2
            info_y = len(self.title)
            self.stdscr.addstr(info_y + 1, info_x, f'Player: {self.player_name}')
            self.stdscr.addstr(info_y + 2, info_x, f'Score: {int(self.scores["score"]):,}', ptk.color_pair(ptk.COLOR_GREEN))
            self.stdscr.addstr(info_y + 3, info_x, f'Level: {int(self.scores.get("level", 1))}', ptk.color_pair(ptk.COLOR_BLUE))
        except Exception:
            pass

    def draw(self):
        self.draw_info()
        # draw obstacles
        try:
            obs_ch = glyph('BLOCK')
        except Exception:
            obs_ch = '#'
        for o in list(self.obstacles):
            ox = int(o['x'])
            oy = int(o['y'])
            h = int(o.get('h', 1))
            for yy in range(h):
                try:
                    if 0 <= oy + yy <= self.height and 0 <= ox <= self.width:
                        self.stdscr.addch(oy + yy, ox, obs_ch, ptk.color_pair(ptk.COLOR_RED) | ptk.A_BOLD)
                except Exception:
                    pass

        # draw player (multi-line art) anchored at player_x, player_y (player_y is top line)
        try:
            frame = self.player_frames[self.frame_index % len(self.player_frames)]
            for i, line in enumerate(frame):
                y = self.player_y + i - (len(frame) // 2)
                x = self.player_x - (len(line) // 2)
                try:
                    self.stdscr.addstr(y, x, line, ptk.color_pair(ptk.COLOR_CYAN) | ptk.A_BOLD)
                except Exception:
                    pass
        except Exception:
            pass

    def step(self, now):
        # advance animation frame periodically
        try:
            if now - self.frame_time > 0.12:
                self.frame_time = now
                self.frame_index = (self.frame_index + 1) % len(self.player_frames)
        except Exception:
            pass

        # spawn obstacles probabilistically; spawn_rate scales with level
        level = int(self.scores.get('level', 1))
        # slightly higher spawn chance per tick with level
        chance = min(0.5, self.spawn_rate + (level - 1) * 0.03)
        if random.random() < chance:
            # obstacle vertical placement within play area (avoid title area)
            oy = random.randint(len(self.title), max(len(self.title), self.height - 2))
            h = random.choice([1, 2]) if level >= 2 else 1
            ox = self.width - 1
            self.obstacles.append({'x': ox, 'y': oy, 'h': h, 'passed': False})

        # move obstacles left
        for o in list(self.obstacles):
            o['x'] -= 1
            # mark passed when they move left of player_x
            if not o.get('passed') and o['x'] < self.player_x:
                o['passed'] = True
                self.scores['score'] += 10
        # remove off-screen
        self.obstacles = [o for o in self.obstacles if o['x'] >= 0]

        # level progression: every 100 points increase level
        score = int(self.scores.get('score', 0))
        new_level = 1 + score // 100
        if new_level != int(self.scores.get('level', 1)):
            self.scores['level'] = new_level
            # speed up tick slightly
            try:
                self.tick = max(0.03, 0.12 - (new_level - 1) * 0.01)
            except Exception:
                pass

        # collision detection: check if any obstacle overlaps player art
        try:
            frame = self.player_frames[self.frame_index % len(self.player_frames)]
            player_coords = set()
            for i, line in enumerate(frame):
                y = self.player_y + i - (len(frame) // 2)
                x0 = self.player_x - (len(line) // 2)
                for xi, ch in enumerate(line):
                    if ch != ' ':
                        player_coords.add((y, x0 + xi))
            for o in self.obstacles:
                ox = int(o['x'])
                oy = int(o['y'])
                h = int(o.get('h', 1))
                for yy in range(h):
                    if (oy + yy, ox) in player_coords:
                        self.over = True
                        try:
                            self.update_high_scores()
                        except Exception:
                            pass
                        return
        except Exception:
            pass

    def movement(self, ch):
        # allow Up/Down or w/s to move the player up/down within play area
        if ch in (ptk.KEY_UP, ord('w')):
            self.player_y = max(len(self.title), self.player_y - 1)
        elif ch in (ptk.KEY_DOWN, ord('s')):
            self.player_y = min(self.height - 1, self.player_y + 1)

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
