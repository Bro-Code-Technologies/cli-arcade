from game_classes import ptk
import random
import os
import math
from collections import deque
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
from game_classes.tools import verify_terminal_size, init_ptk, is_enter_key

TITLE = [
     '___________                  .__              .__    ___________           ___.   .__          ',
    r'\__    ___/__________  _____ |__| ____ _____  |  |   \__    ___/_ __  _____\_ |__ |  |   ____  ',
    r'  |    |_/ __ \_  __ \/     \|  |/    \\__  \ |  |     |    | |  |  \/     \| __ \|  | _/ __ \ ',
    r'  |    |\  ___/|  | \/  Y Y  \  |   |  \/ __ \|  |__   |    | |  |  /  Y Y  \ \_\ \  |_\  ___/ ',
    r'  |____| \___  >__|  |__|_|  /__|___|  (____  /____/   |____| |____/|__|_|  /___  /____/\___  >',
    r'             \/            \/        \/     \/                            \/    \/          \/ '
]

# minimum terminal size required to run this game (cols, rows)
MIN_COLS = 100
MIN_ROWS = 30

SHAPES = {
  'I': [[(0,1),(1,1),(2,1),(3,1)], [(2,0),(2,1),(2,2),(2,3)]],
  'O': [[(0,0),(1,0),(0,1),(1,1)]],
  'T': [[(1,0),(0,1),(1,1),(2,1)], [(1,0),(1,1),(2,1),(1,2)], [(0,1),(1,1),(2,1),(1,2)], [(1,0),(0,1),(1,1),(1,2)]],
  'S': [[(1,0),(2,0),(0,1),(1,1)], [(1,0),(1,1),(2,1),(2,2)]],
  'Z': [[(0,0),(1,0),(1,1),(2,1)], [(2,0),(1,1),(2,1),(1,2)]],
  'J': [[(0,0),(0,1),(1,1),(2,1)], [(1,0),(2,0),(1,1),(1,2)], [(0,1),(1,1),(2,1),(2,2)], [(1,0),(1,1),(0,2),(1,2)]],
  'L': [[(2,0),(0,1),(1,1),(2,1)], [(1,0),(1,1),(1,2),(2,2)], [(0,1),(1,1),(2,1),(0,2)], [(0,0),(1,0),(1,1),(1,2)]],
}

COLORS = {
  'I': ptk.COLOR_WHITE,
  'O': ptk.COLOR_BLUE,
  'T': ptk.COLOR_CYAN,
  'S': ptk.COLOR_GREEN,
  'Z': ptk.COLOR_RED,
  'J': ptk.COLOR_MAGENTA,
  'L': ptk.COLOR_YELLOW,
}

class Piece:
  def __init__(self, shape):
    self.shape = shape
    self.rots = SHAPES[shape]
    self.rot = 0
    self.blocks = self.rots[self.rot]
    # shift spawn one column right to account for permanent left wall
    self.x = 9
    self.y = 0

  def rotate(self, board):
    old = self.rot
    self.rot = (self.rot + 1) % len(self.rots)
    self.blocks = self.rots[self.rot]
    if self.collides(board):
      self.rot = old
      self.blocks = self.rots[self.rot]

  def collides(self, board, dx=0, dy=0):
    for bx, by in self.blocks:
      x = self.x + bx + dx
      y = self.y + by + dy
      if x < 0 or x >= len(board[0]) or y < 0 or y >= len(board):
        return True
      if board[y][x] != ' ':
        return True
    return False

  def move(self, dx, dy, board):
    if not self.collides(board, dx, dy):
      self.x += dx
      self.y += dy
      return True
    return False

class Game(GameBase):
    def __init__(self, stdscr, player_name='Player'):
        self.title = TITLE
        self.highscores = HighScores('terminal_tumble', {
            'score': {'player': 'Player', 'value': 0},
            'lines': {'player': 'Player', 'value': 0},
            'level': {'player': 'Player', 'value': 1},
        })
        super().__init__(stdscr, player_name, 0.5, ptk.COLOR_RED)
        self.msg_height = self.height - 22
        self.init_scores([['score', 0], ['lines', 0], ['level', 1]])

        # game state
        # board with a permanent left wall in column 0
        self.board = [[' ' for _ in range(20)] for _ in range(self.height - 6)]
        for y in range(self.height - 6):
            self.board[y][0] = 'W'
        self.current = self.next_piece()
        self.next = self.next_piece()
        self.drop_timer = 0
        self.msg_log = deque(maxlen=self.msg_height)

    def push_message(self, text, color_const=ptk.COLOR_WHITE):
        try:
            self.msg_log.append((text, color_const))
        except Exception:
            pass
        
    def handle_new_highs(self, metric):
      if not self.new_highs[metric]:
        cap_metric = metric.capitalize()
        self.push_message(f'New High {cap_metric}!', ptk.COLOR_YELLOW)
      super().handle_new_highs(metric)

    def next_piece(self):
        return Piece(random.choice(list(SHAPES.keys())))

    def lock_piece(self):
        for bx, by in self.current.blocks:
            x = self.current.x + bx
            y = self.current.y + by
            if 0 <= y < self.height - 6 and 0 <= x < len(self.board[0]):
                self.board[y][x] = self.current.shape
        cleared = self.clear_lines()
        self.current = self.next
        self.next = self.next_piece()
        if self.current.collides(self.board):
          self.over = True
        return cleared

    def clear_lines(self):
        # preserve left wall when clearing rows
        new_board = [row for row in self.board if any(c == ' ' for c in row)]
        cleared = self.height - 6 - len(new_board)
        for _ in range(cleared):
            new_row = [' ' for _ in range(len(self.board[0]))]
            new_row[0] = 'W'
            new_board.insert(0, new_row)
        # ensure existing rows keep the wall in column 0
        for row in new_board:
            row[0] = 'W'
        self.board = new_board
        if cleared:
            # update lines and level first
            self.scores['lines'] += cleared
            self.scores['level'] = 1 + self.scores['lines'] // 10
            # tick based on level
            self.tick = max(0.05, self.tick - (self.scores['level'] - 1)*0.04)
            # exponential points based on level: slow start, grows faster later
            multiplier = math.exp(self.scores['level'] / 10.0)
            base_points = 100 * cleared
            points = int(base_points * multiplier)
            # push a rolling message for this clear
            label = ''
            color = ptk.COLOR_WHITE
            if cleared == 2:
                label = 'Double!'
                color = ptk.COLOR_CYAN
                points = int(points * 1.5)
            elif cleared == 3:
                label = 'Triple!'
                color = ptk.COLOR_BLUE
                points = int(points * 2.0)
            elif cleared == 4:
                label = 'Full Stack!'
                color = ptk.COLOR_GREEN
                points = int(points * 3.0)
            self.scores['score'] += points
            self.push_message(f'+{points} {label}', color)
        return cleared

    def hard_drop(self):
        slam_mult = 0.1
        # exponential accumulation: grow slam_mult each dropped row
        # simple rule: slam_mult = slam_mult * 1.25 + 0.1
        while self.current.move(0,1,self.board):
            slam_mult = slam_mult * (1 + self.scores['level'] / 10.0)
        # lock_piece now returns number of cleared lines
        cleared = self.lock_piece()
        if cleared and cleared > 0:
            # compute slam bonus: scales with cleared lines and level
            multiplier = math.exp(self.scores['level'] / 10.0)
            base_points = 100 * cleared
            # slam multiplier gives larger bonus for more lines (0.5,1.0,1.5,2.0)
            slam_bonus = cleared * slam_mult
            bonus = int(base_points * multiplier * slam_bonus)
            # double the slam bonus if it's a 4-line slam
            if cleared == 4:
                bonus *= 2
            self.scores['score'] += bonus
            # push slam bonus message if any
            if bonus > 0:
                self.push_message(f'+{bonus} Slam Bonus!', ptk.COLOR_MAGENTA)
                try:
                    self.update_high_scores()
                except Exception:
                    pass
                
    def draw_info(self):
        info_y = len(self.title)
        # draw next-piece preview above the score
        try:
            preview_x = 43
            preview_y = info_y
            # draw the next-piece in the preview column (no label)
            piece_x = preview_x
            try:
                # clear a 4x4 preview area to the right of the label
                for ry in range(4):
                    for rx in range(4):
                        try:
                            self.stdscr.addstr(preview_y + ry, piece_x + rx*2, '  ')
                        except Exception:
                            pass
                # draw the next piece
                for bx, by in self.next.blocks:
                    px = piece_x + bx*2
                    py = preview_y + by
                    if py >= 0 and px >= 0:
                        color = COLORS.get(self.next.shape, 1)
                        try:
                            self.stdscr.addstr(py, px, '[]', ptk.color_pair(color))
                        except Exception:
                            try:
                                self.stdscr.addstr(py, px, '[]')
                            except Exception:
                                pass
            except Exception:
                pass
        except Exception:
            pass
        self.stdscr.addstr(info_y + 0 , 55, f'High Score: {int(self.high_scores["score"]["value"]):,} ({self.high_scores["score"]["player"]})', ptk.color_pair(ptk.COLOR_GREEN))
        self.stdscr.addstr(info_y + 1 , 55, f'High Lines: {int(self.high_scores["lines"]["value"]):,} ({self.high_scores["lines"]["player"]})', ptk.color_pair(ptk.COLOR_BLUE))
        self.stdscr.addstr(info_y + 2 , 55, f'High Level: {int(self.high_scores["level"]["value"]):,} ({self.high_scores["level"]["player"]})', ptk.color_pair(ptk.COLOR_MAGENTA))
        # player name
        info_y += 4
        try:
            self.stdscr.addstr(info_y, 43, f'Player: {self.player_name}', ptk.A_BOLD)
        except Exception:
            pass
        self.stdscr.addstr(info_y + 1, 43, '====================================================')
        self.stdscr.addstr(info_y + 2, 43, f'Score: {int(self.scores["score"]):,}', ptk.color_pair(ptk.COLOR_GREEN))
        self.stdscr.addstr(info_y + 3, 43, f'Lines: {int(self.scores["lines"]):,}', ptk.color_pair(ptk.COLOR_BLUE))
        self.stdscr.addstr(info_y + 4, 43, f'Level: {int(self.scores["level"]):,}', ptk.color_pair(ptk.COLOR_MAGENTA))

        self.stdscr.addstr(info_y + 5, 43, '====================================================')
        # draw rolling message log (most recent at top)
        info_y += 6
        try:
            preview_x = 43
            start_y = info_y
            msgs = list(self.msg_log)
            # clear area first
            for i in range(self.msg_height):
                try:
                    self.stdscr.addstr(start_y + i, preview_x, ' ' * 40)
                except Exception:
                    pass
            # display newest first
            for idx, (text, color_const) in enumerate(reversed(msgs)):
                if idx >= self.msg_height:
                    break
                y = start_y + idx
                try:
                    self.stdscr.addstr(y, preview_x, text, ptk.color_pair(color_const))
                except Exception:
                    try:
                        self.stdscr.addstr(y, preview_x, text)
                    except Exception:
                        pass
        except Exception:
            pass
        info_y += self.msg_height
        self.stdscr.addstr(info_y - 1, 43, '====================================================')
        self.stdscr.addstr(info_y + 0, 43, '←     | a     : Left')
        self.stdscr.addstr(info_y + 1, 43, '→     | d     : Right')
        self.stdscr.addstr(info_y + 2, 43, '↑     | w     : Rotate')
        self.stdscr.addstr(info_y + 3, 43, '↓     | s     : Down (soft drop)')
        self.stdscr.addstr(info_y + 4, 43, 'SPACE | ENTER : Slam (hard drop)')
        self.stdscr.addstr(info_y + 5, 43, 'BACKSPACE     : Pause/Resume')
        self.stdscr.addstr(info_y + 6, 43, 'ESC           : Quit')

    def draw(self):
        # draw roof (one line) above the board with a centered opening
        y_roof = len(self.title) - 1
        if y_roof >= 0:
            open_w = min(max(0, 6), len(self.board[0]))
            open_start = (len(self.board[0]) - open_w) // 2
            open_end = open_start + open_w
            for x in range(len(self.board[0])):
                try:
                    if open_start <= x < open_end:
                        # leave opening
                        self.stdscr.addstr(y_roof, x*2+1, '  ')
                    else:
                        self.stdscr.addstr(y_roof, x*2+1, '==')
                except Exception:
                    pass
        # draw board with top margin
        for y in range(self.height - 6):
            y_off = y + y_roof + 1
            for x in range(len(self.board[0])):
                ch = self.board[y][x]
                if ch == 'W':
                    # permanent left wall
                    self.stdscr.addstr(y_off, x*2, ' |')
                elif ch != ' ':
                    color = COLORS.get(ch, 1)
                    attr = ptk.color_pair(color)
                    if ch == 'J':
                        attr |= ptk.A_DIM
                    self.stdscr.addstr(y_off, x*2, '[]', attr)
                else:
                    self.stdscr.addstr(y_off, x*2, '  ')
        # draw current (apply top margin)
        for bx, by in self.current.blocks:
            x = self.current.x + bx
            y = self.current.y + by
            y_off = y + len(self.title)
            if 0 <= y < self.height - 6 and 0 <= x < len(self.board[0]):
                color = COLORS.get(self.current.shape, 1)
                attr = ptk.color_pair(color)
                if self.current.shape == 'J':
                    attr |= ptk.A_DIM
                self.stdscr.addstr(y_off, x*2, '[]', attr)

        # draw borders and (shifted by top margin)
        for y in range(self.height - 6):
            y_off = y + len(self.title)
            self.stdscr.addstr(y_off, len(self.board[0])*2, '|')

        # draw floor below the board using '='
        try:
            floor_y = len(self.title) + self.height - 6
            for x in range(len(self.board[0])):
                self.stdscr.addstr(floor_y, x*2+1, '==')
        except Exception:
            pass
        self.draw_info()
    
    def step(self, now):
      if not self.current.move(0,1,self.board):
          self.lock_piece()

    def movement(self, ch):
      if ch in (ptk.KEY_LEFT, ord('a')):
        self.current.move(-1,0,self.board)
      elif ch in (ptk.KEY_RIGHT, ord('d')):
        self.current.move(1,0,self.board)
      elif ch in (ptk.KEY_DOWN, ord('s')):
        self.current.move(0,1,self.board)
      elif ch in (ptk.KEY_UP, ord('w')):
        self.current.rotate(self.board)
      elif is_enter_key(ch) or ch == ord(' '):
        self.hard_drop()

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
