from game_classes import ptk
import time
from game_classes.tools import get_terminal_size

class GameBase:
  def __init__(self, stdscr, player_name, tick, color=ptk.COLOR_GREEN):
    self.stdscr = stdscr
    self.player_name = player_name
    self.tick = tick
    self.color = color
    self.high_scores = self.highscores.load()
    self.width, self.height = get_terminal_size(stdscr)
    self.over = False
    self.paused = False

  def init_scores(self, list=[['score', 0]]):
    self.new_highs = {}
    self.scores = {}
    for metric, initial in list:
      self.new_highs[metric] = False
      self.scores[metric] = initial
		
  def update_player_name(self, name):
    self.player_name = name
        
  def handle_new_highs(self, metric):
    self.new_highs[metric] = True
        
  def check_and_set_scores(self, metric='score'):
    updated = False
    try:
      if self.scores[metric] > self.high_scores[metric].get('value', 0):
        self.high_scores[metric]['value'] = int(self.scores[metric])
        self.high_scores[metric]['player'] = getattr(self, 'player_name', 'Player')
        updated = True
        self.handle_new_highs(metric)
    except Exception as e:
      updated = False
    return updated

  def update_high_scores(self):
    """Update the `high_scores` dict if current player exceeds any metric and save."""
    updated = False
    try:
      for metric in self.scores:
        updated |= self.check_and_set_scores(metric)
    except Exception:
      updated = False
    if updated:
      try:
        self.highscores.save(self.high_scores)
      except Exception:
        pass
    return updated
  
  def step(self, now):
    pass

  def movement(self, ch):
    pass

  def events(self, ch):
    if ch != -1:
      if ch == 27:
        return True
      if not getattr(self, 'over', False):
        # toggle pause on Backspace
        if ch in (ptk.KEY_BACKSPACE, 127, 8):
          self.paused = not getattr(self, 'paused', False)
        # movement only when not paused
        elif not getattr(self, 'paused', False):
          self.movement(ch)
    return False
  
  def draw_game_status(self, msg):
    try:
      py = max(0, min(self.height, self.height // 2))
      px = max(0, (self.width - len(msg)) // 2)
      self.stdscr.addstr(py, px, msg, ptk.color_pair(ptk.COLOR_RED) | ptk.A_BOLD)
    except Exception:
      pass

  def pre_draw(self):
    self.stdscr.clear()
    try:
      for i, line in enumerate(self.title):
        try:
          self.stdscr.addstr(i, 0, line, ptk.color_pair(self.color) | ptk.A_BOLD)
        except Exception:
          pass
    except Exception:
      pass

  def draw(self):
    pass

  def post_draw(self):
    # overlay: game-over takes precedence over paused
    if getattr(self, 'over', False):
      self.draw_game_status('GAME OVER')
    elif getattr(self, 'paused', False):
      self.draw_game_status('PAUSED')
    self.stdscr.refresh()

  def run(self):
    last = time.time()
    while True:
      now = time.time()
      if self.events(self.stdscr.getch()):
        break
      if now - last > self.tick and not getattr(self, 'over', False) and not getattr(self, 'paused', False):
        self.step(now)
        last = now
      self.pre_draw()
      self.draw()
      self.post_draw()
      try:
        self.update_high_scores()
      except Exception:
        pass
      time.sleep(0.01)