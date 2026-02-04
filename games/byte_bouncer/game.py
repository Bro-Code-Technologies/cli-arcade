from game_classes import ptk
import os
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
from game_classes.tools import glyph, verify_terminal_size, init_ptk, clamp

TITLE = [
     '  ____  _  _  ____  ____    ____   __   _  _  __ _   ___  ____  ____  ',
    r' (  _ \( \/ )(_  _)(  __)  (  _ \ /  \ / )( \(  ( \ / __)(  __)(  _ \ ',
    r'  ) _ ( )  /   )(   ) _)    ) _ ((  O )) \/ (/    /( (__  ) _)  )   / ',
    r' (____/(__/   (__) (____)  (____/ \__/ \____/\_)__) \___)(____)(__\_) '
]

# minimum terminal size required to run this game (cols, rows)
MIN_COLS = 70
MIN_ROWS = 20

class Game(GameBase):
    def __init__(self, stdscr, player_name='Player'):
      self.title = TITLE
      self.highscores = HighScores('byte_bouncer', {
          'score': {'player': 'Player', 'value': 0},
          'level': {'player': 'Player', 'value': 1},
      })
      super().__init__(stdscr, player_name, 0.12, ptk.COLOR_GREEN)
      self.init_scores([['score', 0], ['level', 1]])

      # game state
      self.count = 0
      # multiple balls support: list of dicts with x,y,vx,vy
      self.balls = [
        { 'x': self.width // 2, 'y': self.height // 2, 'vx': random.choice([-1,1]), 'vy': -1 }
      ]
      self.paddle_w = 30
      self.paddle_x = self.width // 2 - self.paddle_w // 2

    def draw_info(self):
      info_x = 2
      info_y = len(self.title)
      try:
        # draw high scores below title
        new_score = ' ***NEW High Score!' if self.new_highs.get('score', False) else ''
        new_level = ' ***NEW High Level!' if self.new_highs.get('level', False) else ''
        self.stdscr.addstr(info_y + 1 , info_x, f'High Score: {int(self.high_scores["score"]["value"]):,} ({self.high_scores["score"]["player"]}){new_score}', ptk.color_pair(ptk.COLOR_GREEN))
        self.stdscr.addstr(info_y + 2 , info_x, f'High Level: {int(self.high_scores["level"]["value"]):,} ({self.high_scores["level"]["player"]}){new_level}', ptk.color_pair(ptk.COLOR_BLUE))

        # draw game info below title
        self.stdscr.addstr(info_y + 4, info_x, f'Player: {self.player_name}')
        self.stdscr.addstr(info_y + 5, info_x, f'Score: {int(self.scores["score"]):,}', ptk.color_pair(ptk.COLOR_GREEN))
        self.stdscr.addstr(info_y + 6, info_x, f'Level: {int(self.scores["level"]):,}', ptk.color_pair(ptk.COLOR_BLUE))

        self.stdscr.addstr(info_y + 8 , info_x, '← | a     : Left')
        self.stdscr.addstr(info_y + 9 , info_x, '→ | d     : Right')
        self.stdscr.addstr(info_y + 10, info_x, 'Backspace : Pause')
        self.stdscr.addstr(info_y + 11, info_x, 'ESC       : Quit')
      except Exception:
        pass

    def draw(self):
      self.draw_info()
      # draw balls
      try:
        for idx, b in enumerate(self.balls):
          try:
            if idx == 0:
              attr = ptk.color_pair(ptk.COLOR_MAGENTA) | ptk.A_BOLD
            else:
              attr = ptk.color_pair(ptk.COLOR_YELLOW) | ptk.A_BOLD
            self.stdscr.addch(int(b['y']), 1 + int(b['x']), glyph('CIRCLE_FILLED', 'O'), attr)
          except Exception:
            pass
      except Exception:
        pass
      # draw paddle
      # draw a green floor along the bottom using the BLOCK glyph, then
      # draw a green right wall. Paddle is drawn on top of the floor.
      try:
        block = glyph('BLOCK')
      except Exception:
        block = '#'
      # floor: across playable width
      for fx in range(0, self.width + 1):
        try:
          self.stdscr.addch(self.height + 1, 1 + fx, block, ptk.color_pair(ptk.COLOR_GREEN))
        except Exception:
          pass
      # right wall: draw from top down to the floor at terminal column (1 + self.width)
      for wy in range(0, self.height + 1):
        try:
          self.stdscr.addch(wy, 1 + self.width, block, ptk.color_pair(ptk.COLOR_GREEN))
        except Exception:
          pass

      for i in range(self.paddle_w):
        x = clamp(self.paddle_x + i, 0, self.width - 1)
        try:
          self.stdscr.addch(self.height, x + 1, '=', ptk.color_pair(ptk.COLOR_GREEN) | ptk.A_BOLD)
        except Exception:
          pass

    def step(self, now):
      # move each ball and handle collisions
      for i, b in enumerate(self.balls[:]):
        b['x'] += b['vx']
        b['y'] += b['vy']
        # collisions with walls
        if b['x'] < 0:
          b['x'] = 0
          b['vx'] *= -1
        elif b['x'] >= self.width:
          b['x'] = self.width - 1
          b['vx'] *= -1
        if b['y'] < 0:
          b['y'] = 0
          b['vy'] *= -1
        # bottom: check paddle
        if b['y'] >= self.height:
          if self.paddle_x <= b['x'] < self.paddle_x + self.paddle_w:
            # bounce
            b['y'] = self.height - 1
            b['vy'] *= -1
            # normalize horizontal velocity to magnitude 1
            if b['vx'] < 0:
              b['vx'] = -1
            elif b['vx'] > 0:
              b['vx'] = 1
            else:
              b['vx'] = random.choice([-1, 1])
            self.scores['score'] += 10 * self.scores['level'] * len(self.balls)
            self.count += 1
            # increase level every 5 successful bounces
            if self.count % 5 == 0:
              self.scores['level'] += 1
              # spawn new ball near center top area
              nb = {
                'x': random.randint(2, max(2, self.width-3)),
                'y': random.randint(2, max(2, self.height - self.height//3)),
                'vx': random.choice([-1,1]),
                'vy': -1
              }
              self.balls.append(nb)
          elif b['x'] == self.paddle_x - 1 and b['vx'] > 0:
            # edge bounce left
            b['y'] = self.height - 1
            b['vy'] *= -1
            b['vx'] *= -1
            self.scores['score'] += 10 * self.scores['level'] * len(self.balls) * 2
            self.count += 1
            # increase level every 5 successful bounces
            if self.count % 5 == 0:
              self.scores['level'] += 1
              # spawn new ball near center top area
              nb = {
                'x': random.randint(2, max(2, self.width-3)),
                'y': random.randint(2, max(2, self.height - self.height//3)),
                'vx': random.choice([-1,1]),
                'vy': -1
              }
              self.balls.append(nb)
          elif b['x'] == self.paddle_x + self.paddle_w and b['vx'] < 0:
            # edge bounce right
            b['y'] = self.height - 1
            b['vy'] *= -1
            b['vx'] *= -1
            self.scores['score'] += 10 * self.scores['level'] * len(self.balls) * 2
            self.count += 1
            # increase level every 5 successful bounces
            if self.count % 5 == 0:
              self.scores['level'] += 1
              # spawn new ball near center top aread
              nb = {
                'x': random.randint(2, max(2, self.width-3)),
                'y': random.randint(2, max(2, self.height - self.height//3)),
                'vx': random.choice([-1,1]),
                'vy': -1
              }
              self.balls.append(nb)
          else:
            b['y'] = self.height + 1
            # if primary ball misses -> game over
            if i == 0:
              self.over = True
              return
            # otherwise remove the extra ball (it contributes to score normally)
            try:
              # find and remove by identity (safer if list has changed)
              self.balls.pop(i)
            except Exception:
              try:
                self.balls.remove(b)
              except Exception:
                pass

    def movement(self, ch):
      if ch in (ptk.KEY_LEFT, ord('a')):
        self.paddle_x = int(clamp(self.paddle_x - 2, 0, self.width - self.paddle_w))
      elif ch in (ptk.KEY_RIGHT, ord('d')):
        self.paddle_x = int(clamp(self.paddle_x + 2, 0, self.width - self.paddle_w))

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