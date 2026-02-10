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
from game_classes.tools import init_ptk, glyph, is_enter_key
import random
import time

TITLE = [                                                                                                                         
  ' ██████  ▄▄▄▄  ▄▄▄▄  ▄▄▄  ▄▄▄▄  ▄▄▄▄▄   ▄█████ ▄▄▄▄▄  ▄▄▄  ▄▄ ▄▄ ▄▄▄▄▄ ▄▄  ▄▄  ▄▄▄▄ ▄▄▄▄▄ ',
  ' ██▄▄   ███▄▄ ██▀▀▀ ██▀██ ██▄█▀ ██▄▄    ▀▀▀▄▄▄ ██▄▄  ██▀██ ██ ██ ██▄▄  ███▄██ ██▀▀▀ ██▄▄  ',
  ' ██▄▄▄▄ ▄▄██▀ ▀████ ██▀██ ██    ██▄▄▄   █████▀ ██▄▄▄ ▀███▀ ▀███▀ ██▄▄▄ ██ ▀██ ▀████ ██▄▄▄ ',
  '                                                       ▀▀                                 '
]

# minimum terminal size required to run this game (cols, rows)
MIN_COLS = 100
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
        self.player_x = max(20, int(self.width * 0.15))
        # remember start x to restore on level-up
        self.start_player_x = int(self.player_x)
        self.player_y = self.height // 2

        # running animation frames (simple multi-line glyphs)
        self.player_frames = [
            [ r'  O  ', r' /|\ ', r' / \ ' ],
            [ r'  O  ', r'  |  ', r'  |  ' ],
        ]
        self.frame_index = 0
        self.frame_time = 0.0

        # obstacles: list of dicts {x, y, w, h, passed}
        self.obstacles = []
        self.spawn_acc = 0.0
        self.spawn_rate = 0.12  # base chance per tick to spawn
        self.last_step = time.time()
        # progression: levels are static for this game (no auto-increment)
        # initial stall: number of ticks to disable player movement at game start
        self.initial_stall_ticks = 30
        self.initial_stall = int(self.initial_stall_ticks)
        self.finish_line = 3
        self.discs = 2
        self.disc_active = False
        self.disc_duration_ticks = 8
        self.disc_timer = 0
        # spawned disc items (collectibles moving left); keep separate from `self.discs` resource count
        self.spawned_discs = []
        self.disc_bonus = 50
        # cooldown (ticks) to avoid immediate repeated disc spawns
        self.disc_spawn_cooldown = 20

    def draw_info(self):
      info_x = 2
      info_y = len(self.title)
      try:
        # draw high scores below title
        new_score = ' ***NEW High Score!' if self.new_highs.get('score', False) else ''
        new_level = ' ***NEW High Level!' if self.new_highs.get('level', False) else ''
        self.stdscr.addstr(info_y + 0, info_x, f'High Score: {int(self.high_scores["score"]["value"]):,} ({self.high_scores["score"]["player"]}){new_score}', ptk.color_pair(ptk.COLOR_GREEN))
        self.stdscr.addstr(info_y + 1, info_x, f'High Level: {int(self.high_scores["level"]["value"]):,} ({self.high_scores["level"]["player"]}){new_level}', ptk.color_pair(ptk.COLOR_BLUE))

        # draw disc indicators
        self.stdscr.addstr(info_y + 2, info_x, glyph('CIRCLE_FILLED', 'O') * self.discs, ptk.color_pair(ptk.COLOR_CYAN) | ptk.A_BOLD)

        # draw game info below title
        self.stdscr.addstr(info_y + 3, info_x, f'Player: {self.player_name}')
        self.stdscr.addstr(info_y + 4, info_x, f'Score: {int(self.scores["score"]):,}', ptk.color_pair(ptk.COLOR_GREEN))
        self.stdscr.addstr(info_y + 5, info_x, f'Level: {int(self.scores["level"]):,}', ptk.color_pair(ptk.COLOR_BLUE))

        self.stdscr.addstr(info_y + 7 , info_x, '↑ | w       : Up')
        self.stdscr.addstr(info_y + 8 , info_x, '↓ | s       : Down')
        self.stdscr.addstr(info_y + 9 , info_x, '← | a       : Left')
        self.stdscr.addstr(info_y + 10, info_x, '→ | d       : Right')
        self.stdscr.addstr(info_y + 11, info_x, 'Enter/Space : Use Disc')
        self.stdscr.addstr(info_y + 12, info_x, 'Backspace   : Pause')
        self.stdscr.addstr(info_y + 13, info_x, 'ESC         : Quit')
      except Exception:
        pass

    def draw(self):
        self.draw_info()
        # draw obstacles
        try:
            obs_ch = glyph('BLOCK')
        except Exception:
            obs_ch = '#'
        # color the rightmost 3 columns as a background panel
        try:
            bg_pair = ptk.color_pair(ptk.COLOR_MAGENTA) | ptk.A_REVERSE
            right_start = max(0, self.width - self.finish_line)
            for col in range(right_start, self.width):
                for ry in range(0, self.height + 1):
                    try:
                        self.stdscr.addch(ry, col, ' ', bg_pair)
                    except Exception:
                        pass
        except Exception:
            pass
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

        # draw spawned discs (collectibles)
        try:
            disc_ch = glyph('CIRCLE_FILLED', 'O')
        except Exception:
            disc_ch = 'o'
        for d in list(self.spawned_discs):
            dx = int(d['x'])
            dy = int(d['y'])
            try:
                if 0 <= dy <= self.height and 0 <= dx <= self.width:
                    self.stdscr.addch(dy, dx, disc_ch, ptk.color_pair(ptk.COLOR_CYAN) | ptk.A_BOLD)
            except Exception:
                pass

        try:
            if getattr(self, 'disc_active', False):
                try:
                    self.stdscr.addch(self.player_y, self.player_x, glyph('CIRCLE_FILLED', 'O'), ptk.color_pair(ptk.COLOR_CYAN) | ptk.A_BOLD)
                except Exception:
                    try:
                        self.stdscr.addstr(self.player_y, self.player_x, glyph('CIRCLE_FILLED', 'O'))
                    except Exception:
                        pass
            else:
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

        # decrement initial stall so obstacles can build up before player moves
        try:
            if getattr(self, 'initial_stall', 0) > 0:
                self.initial_stall = max(0, int(self.initial_stall) - 1)
        except Exception:
            pass

        try:
            if getattr(self, 'disc_timer', 0) > 0:
                self.disc_timer = max(0, int(self.disc_timer) - 1)
                if self.disc_timer <= 0:
                    self.disc_active = False
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
            # spawn a few columns in from the right edge so blocks appear "in-screen"
            ox = max(0, self.width - self.finish_line)
            self.obstacles.append({'x': ox, 'y': oy, 'h': h, 'passed': False})

        # spawn collectible discs occasionally (with cooldown to avoid clusters)
        if getattr(self, 'disc_spawn_cooldown', 0) <= 0:
            dy = random.randint(len(self.title), max(len(self.title), self.height - 2))
            dx = max(0, self.width - self.finish_line)
            self.spawned_discs.append({'x': dx, 'y': dy})
            self.disc_spawn_cooldown = random.randint(500, 10000)
        else:
            self.disc_spawn_cooldown = max(0, int(self.disc_spawn_cooldown) - 1)
        # move obstacles left
        for o in list(self.obstacles):
            o['x'] -= 1
            # mark passed when they move left of player_x
            if not o.get('passed') and o['x'] < self.player_x:
                o['passed'] = True
                self.scores['score'] += 10 * (1 + (level - 1) * 0.5) * max((getattr(self, 'player_x', 1) * 0.03), 1)
        # remove off-screen
        self.obstacles = [o for o in self.obstacles if o['x'] >= 0]

        # move spawned discs left and remove off-screen
        for d in list(self.spawned_discs):
            d['x'] -= 1
        self.spawned_discs = [d for d in self.spawned_discs if d['x'] >= 0]

        # when obstacles pass the player, count them and increase level
        # after reaching the current requirement; requirement increases by 10% each level
        try:
            # handled when marking 'passed' above; adjust tick here in case level changed elsewhere
            level = int(self.scores.get('level', 1))
            # ensure tick reflects level
            try:
                self.tick = max(0.03, 0.12 - (level - 1) * 0.01)
            except Exception:
                pass
        except Exception:
            pass

        # collision detection: check if any obstacle overlaps player art
        try:
            player_coords = set()
            if getattr(self, 'disc_active', False):
                player_coords.add((self.player_y, self.player_x))
            else:
                frame = self.player_frames[self.frame_index % len(self.player_frames)]
                for i, line in enumerate(frame):
                    y = self.player_y + i - (len(frame) // 2)
                    x0 = self.player_x - (len(line) // 2)
                    for xi, ch in enumerate(line):
                        if ch != ' ':
                            player_coords.add((y, x0 + xi))
            # collect spawned discs if overlapping player
            try:
                for d in list(self.spawned_discs):
                    dx = int(d['x'])
                    dy = int(d['y'])
                    if (dy, dx) in player_coords:
                        try:
                            # increase resource count (`self.discs`) up to a cap
                            cur = int(getattr(self, 'discs', 0))
                            cap = 25
                            if cur < cap:
                                try:
                                    self.discs = cur + 1
                                except Exception:
                                    pass
                            # award bonus score
                            try:
                                self.scores['score'] += int(getattr(self, 'disc_bonus', 50)) * level * self.player_x * 0.03
                            except Exception:
                                pass
                        except Exception:
                            pass
                        try:
                            self.spawned_discs.remove(d)
                        except Exception:
                            pass
            except Exception:
                pass

            # obstacle collisions cause game over
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
        # prevent movement while initial stall is active
        try:
            if getattr(self, 'initial_stall', 0) > 0:
                return
        except Exception:
            pass
        # disc toggle on Enter or Space; limited uses per level
        try:
            if is_enter_key(ch) or ch == ord(' '):
                if getattr(self, 'disc_active', False):
                    self.disc_active = False
                    self.disc_timer = 0
                else:
                    if getattr(self, 'discs', 0) > 0:
                        self.disc_active = True
                        try:
                            self.discs -= 1
                        except Exception:
                            pass
                        try:
                            self.disc_timer = int(getattr(self, 'disc_duration_ticks', 8))
                        except Exception:
                            self.disc_timer = 8
                return
        except Exception:
            pass

        # allow Up/Down or w/s to move the player up/down within play area
        if ch in (ptk.KEY_UP, ord('w')):
            self.player_y = max(len(self.title), self.player_y - 1)
        elif ch in (ptk.KEY_DOWN, ord('s')):
            self.player_y = min(self.height - 1, self.player_y + 1)
        # allow left/right movement within a reasonable left-side range
        elif ch in (ptk.KEY_LEFT, ord('a')):
            self.player_x = max(2, self.player_x - 2)
        elif ch in (ptk.KEY_RIGHT, ord('d')):
            self.player_x = min(self.width - 2, self.player_x + 2)
            # if player reaches the finish-line region, advance level (restart board but keep score)
            try:
                if self.player_x >= max(0, self.width - int(self.finish_line)):
                    try:
                        self._level_up()
                    except Exception:
                        pass
            except Exception:
                pass

    def _level_up(self):
        """Increase level, clear the board, and reset player position while keeping score."""
        try:
            cur = int(self.scores.get('level', 1))
        except Exception:
            cur = 1
        new_level = cur + 1
        try:
            self.scores['level'] = new_level
        except Exception:
            pass
        # clear obstacles and reset counters
        try:
            self.obstacles = []
            # reset player position to starting X and center Y
            self.player_x = int(getattr(self, 'start_player_x', max(6, int(self.width * 0.15))))
            self.player_y = max(len(self.title), min(self.height // 2, self.player_y))
            # short stall so the board can refill
            self.initial_stall = int(getattr(self, 'initial_stall_ticks', 10))
            # speed up tick modestly
            try:
                self.tick = max(0.03, 0.12 - (new_level - 1) * 0.01)
            except Exception:
                pass
            # increase spawn rate a bit
            try:
                self.spawn_rate = min(0.6, getattr(self, 'spawn_rate', 0.12) + 0.03)
            except Exception:
                pass
            try:
                self.discs = min(25, int(getattr(self, 'discs', 2) + 1))
                self.disc_active = False
                self.disc_timer = 0
            except Exception:
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
