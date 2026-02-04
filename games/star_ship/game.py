from game_classes import ptk
import os
import time
import random
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
from game_classes.tools import verify_terminal_size, init_ptk, is_enter_key, glyph

TITLE = [
   "    ______             ______   _     ",
   "   / __/ /____ _____  / __/ /  (_)__  ",
  r"  _\ \/ __/ _ `/ __/ _\ \/ _ \/ / _ \ ",
  r" /___/\__/\_,_/_/   /___/_//_/_/ .__/ ",
  "                            /_/       "                            
]

class Game(GameBase):
    def __init__(self, stdscr, player_name='Player'):
      self.title = TITLE
      self.highscores = HighScores('star_ship', {
          'score': {'player': 'Player', 'value': 0},
          'stars': {'player': 'Player', 'value': 1},
          'length': {'player': 'Player', 'value': 3},
      })
      super().__init__(stdscr, player_name, 0.12, ptk.COLOR_GREEN)
      self.init_scores([['score', 0], ['stars', 0], ['length', 0]])

      # game state
      self.special = None
      self.special_expire = None
      self.next_special_at = time.time() + random.uniform(8, 18)
      self.dir = (0, 1)
      self.stars = []
      cy = self.height // 2
      cx = self.width // 2
      self.ship = [(cy, cx - i) for i in range(3)]
      self.dir = (0, 1)
      self.place_star(count=1)

    def place_star(self, count=1):
      """Place `count` yellow stars in free locations."""
      attempts = 0
      placed = 0
      while placed < count and attempts < 5000:
        y = random.randint(0, max(0, self.height - 1))
        x = random.randint(0, max(0, self.width - 1))
        coord = (y, x)
        # avoid ship, existing stars, and special
        if coord in self.ship or coord in self.stars or (self.special is not None and coord == self.special):
          attempts += 1
          continue
        self.stars.append(coord)
        self.scores['stars'] = len(self.stars)
        placed += 1
        attempts += 1
      return

    def place_special(self):
      """Place a single magenta special star and set its expiry."""
      attempts = 0
      while attempts < 2000:
        y = random.randint(0, max(0, self.height - 1))
        x = random.randint(0, max(0, self.width - 1))
        coord = (y, x)
        if coord in self.ship or coord in self.stars or (self.special is not None and coord == self.special):
          attempts += 1
          continue
        self.special = coord
        # Lifetime scales with terminal size (width + height).
        # Use 0.035s per column/row, clamped to a sensible range. 
        size = getattr(self, 'width', 0) + getattr(self, 'height', 0)
        lifetime = size * 0.035 # HIGHER = EASIER
        self.special_expire = time.time() + lifetime
        return
      # failed to place
      self.special = None
      self.special_expire = None
      return

    def draw_info(self):
      try:
        info_x = 2
        info_y = len(self.title)

        # draw high scores below title
        new_score = ' ***NEW High Score!' if self.new_highs.get('score', False) else ''
        self.stdscr.addstr(info_y + 0, info_x, f'High Score: {int(self.high_scores["score"]["value"]):,} ({self.high_scores["score"]["player"]}){new_score}', ptk.color_pair(ptk.COLOR_GREEN))
        new_ship_length = ' ***NEW Longest Ship!' if self.new_highs.get('length', False) else ''
        self.stdscr.addstr(info_y + 1, info_x, f'Longest Ship: {int(self.high_scores["length"]["value"]):,} ({self.high_scores["length"]["player"]}){new_ship_length}', ptk.color_pair(ptk.COLOR_BLUE))
        new_stars = ' ***NEW Most Stars!' if self.new_highs.get('stars', False) else ''
        self.stdscr.addstr(info_y + 2, info_x, f'Most Stars: {int(self.high_scores["stars"]["value"]):,} ({self.high_scores["stars"]["player"]}){new_stars}', ptk.color_pair(ptk.COLOR_BLUE))

        # draw game info below title
        self.stdscr.addstr(info_y + 4, info_x, f'Player: {self.player_name}')
        self.stdscr.addstr(info_y + 5, info_x, f'Score: {int(self.scores["score"]):,}', ptk.color_pair(ptk.COLOR_GREEN))
        self.stdscr.addstr(info_y + 6, info_x, f'Ship Length: {int(self.scores["length"]):,}', ptk.color_pair(ptk.COLOR_BLUE))
        self.stdscr.addstr(info_y + 7, info_x, f'Stars: {int(self.scores["stars"]):,}', ptk.color_pair(ptk.COLOR_BLUE))

        self.stdscr.addstr(info_y + 9 , info_x, '↑ | w     : Up')
        self.stdscr.addstr(info_y + 10, info_x, '← | a     : Left')
        self.stdscr.addstr(info_y + 11, info_x, '↓ | s     : Down')
        self.stdscr.addstr(info_y + 12, info_x, '→ | d     : Right')
        self.stdscr.addstr(info_y + 13, info_x, 'Backspace : Pause')
        self.stdscr.addstr(info_y + 14, info_x, 'ESC       : Quit')
      except Exception:
        pass

    def draw(self):
      self.draw_info()
      # draw game elements (ship + star) on top of title/info
      try:
        # draw yellow stars
        for fy, fx in list(getattr(self, 'stars', [])):
          self.stdscr.addch(fy, fx, '*', ptk.color_pair(ptk.COLOR_YELLOW) | ptk.A_BOLD)
        # draw special magenta (if present)
        if getattr(self, 'special', None) is not None:
          sy, sx = self.special
          self.stdscr.addch(sy, sx, glyph('CIRCLE_FILLED'), ptk.color_pair(ptk.COLOR_MAGENTA) | ptk.A_BOLD)
        # ship: head and body
        for idx, (sy, sx) in enumerate(self.ship):
          try:
            if idx == 0:
              self.stdscr.addch(sy, sx, glyph('CIRCLE_FILLED'), ptk.color_pair(ptk.COLOR_GREEN) | ptk.A_BOLD)
            else:
              self.stdscr.addch(sy, sx, glyph('CIRCLE_FILLED'), ptk.color_pair(ptk.COLOR_BLUE))
          except Exception:
            pass
      except Exception:
        pass

    def step(self, now):
      # auto-spawn special star when time reached
      try:
        if getattr(self, 'special', None) is None and getattr(self, 'next_special_at', 0) and now >= self.next_special_at:
          self.place_special()
      except Exception:
        pass
      # ensure special expires even if paused
      try:
        if getattr(self, 'special', None) is not None and getattr(self, 'special_expire', None) is not None and now >= self.special_expire:
          self.special = None
          self.special_expire = None
          self.next_special_at = now + random.uniform(8, 18)
      except Exception:
        pass

      # compute next head position
      if not self.ship:
        return
      hy, hx = self.ship[0]
      dy, dx = self.dir
      nh, nx = hy + dy, hx + dx
      # check bounds (terminal edges are boundaries)
      if nh < 0 or nh >= self.height or nx < 0 or nx >= self.width:
        self.over = True
        return
      # self-collision
      if (nh, nx) in self.ship:
        self.over = True
        return
      # move head
      self.ship.insert(0, (nh, nx))
      # eating: normal yellow stars
      if (nh, nx) in self.stars:
        try:
          self.stars.remove((nh, nx))
        except Exception:
          pass
        self.scores['score'] = int(self.scores['score']) + 10
        # maintain star by placing one new yellow
        self.place_star(count=1)
        # do not pop tail (grow by 1)
        return
      # special magenta eaten
      if self.special is not None and (nh, nx) == self.special:
        # award larger bonus by yellow star qty
        self.scores['score'] = int(self.scores['score']) + 50 * len(self.stars)
        # spawn 2 yellow stars
        self.place_star(count=2)
        # immediately spawn another magenta special
        self.place_special()
        return
      else:
        # normal move: remove tail
        try:
          self.ship.pop()
        except Exception:
          pass
        # if special expired, clear it and schedule next
        now = time.time()
        if self.special is not None and self.special_expire is not None and now >= self.special_expire:
          self.special = None
          self.special_expire = None
          self.next_special_at = now + random.uniform(8, 18)
      self.scores['length'] = len(self.ship)

    def movement(self, ch):
      new_dir = None
      if ch in (ptk.KEY_UP, ord('w')):
        new_dir = (-1, 0)
      elif ch in (ptk.KEY_DOWN, ord('s')):
        new_dir = (1, 0)
      elif ch in (ptk.KEY_LEFT, ord('a')):
        new_dir = (0, -1)
      elif ch in (ptk.KEY_RIGHT, ord('d')):
        new_dir = (0, 1)
      if new_dir:
        # prevent immediate 180-degree turns
        cy, cx = self.dir
        if (new_dir[0], new_dir[1]) != (-cy, -cx):
          self.dir = new_dir

def main(stdscr):
  verify_terminal_size('Star Ship')
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