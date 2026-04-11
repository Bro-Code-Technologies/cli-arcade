"""
games/star_ship_2/game.py  —  Star Ship 2: 2-4 player real-time multiplayer
"""
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
from game_classes.multiplayer_base import MultiplayerGameBase
from game_classes.tools import init_ptk, glyph

IS_MULTIPLAYER = True
          
TITLE = [
   "    ______             ______   _     ____    ",
   "   / __/ /____ _____  / __/ /  (_)__  \__ \   ",
  r"  _\ \/ __/ _ `/ __/ _\ \/ _ \/ / _ \   / /_  ",
  r" /___/\__/\_,_/_/   /___/_//_/_/ .__/   \___\ ",
   "                            /_/                "                            
]

DESCRIPTION = """Real-time multiplayer Star Ship!
2-4 players share an arena — collect stars, dodge rivals, be the last ship flying!
Press Enter to go to the lobby and find opponents."""

MIN_COLS = 80
MIN_ROWS = 22

# Slot color palette (Green=0, Blue=1, Yellow=2, Magenta=3)
SLOT_COLORS = [ptk.COLOR_GREEN, ptk.COLOR_BLUE, ptk.COLOR_YELLOW, ptk.COLOR_MAGENTA]


class Game(MultiplayerGameBase):
    def __init__(self, stdscr, player_name='Player', socket_client=None, game_data=None):
        self.title = TITLE

        self.highscores = HighScores('star_ship_2', {
            'score': {'player': 'Player', 'value': 0},
            'wins':  {'player': 'Player', 'value': 0},
        })

        game_data = game_data or {}
        super().__init__(stdscr, player_name, socket_client, game_data, tick=0.10)

        self.init_scores([['score', 0], ['wins', 0]])

        # Rendering state — updated by on_game_state()
        self._players = []      # list of player dicts from server
        self._stars = []        # list of {row, col, special}
        self._special_star = None
        self._player_died_msgs = []  # [(slot, cause, until)]
        self._error_msg = ''
        self._error_until = 0.0

        # Arena offset within the terminal
        # Ships render at row=0 (ships can overlap the info panel text — intentional,
        # matching the original Star Ship single-player layout).
        self._info_rows = 0

    # ── Network callbacks ──────────────────────────────────────────────────────

    def on_game_state(self, state):
        self._players = state.get('players', self._players)
        self._stars = state.get('stars', self._stars)
        self._special_star = state.get('specialStar')
        # Update our own score from server state for high score tracking
        my = next((p for p in self._players if p.get('slot') == self.my_slot), None)
        if my:
            self.scores['score'] = my.get('score', 0)

    def on_game_over(self, results):
        super().on_game_over(results)
        # Check if we won
        rankings = results.get('rankings', [])
        if rankings and rankings[0].get('slot') == self.my_slot:
            self.scores['wins'] = int(self.scores.get('wins', 0)) + 1
        self.update_high_scores()

    def on_player_died(self, data):
        slot = data.get('slot', -1)
        cause = data.get('cause', '')
        import time as _time
        self._player_died_msgs.append((slot, cause, _time.time() + 2.5))

    # ── Input ─────────────────────────────────────────────────────────────────

    def movement(self, ch):
        direction = None
        if ch in (ptk.KEY_UP, ord('w')):
            direction = [-1, 0]
        elif ch in (ptk.KEY_DOWN, ord('s')):
            direction = [1, 0]
        elif ch in (ptk.KEY_LEFT, ord('a')):
            direction = [0, -1]
        elif ch in (ptk.KEY_RIGHT, ord('d')):
            direction = [0, 1]
        if direction is not None:
            self.send_input({'direction': direction, 'tick': 0})

    def step(self, now):
        pass  # Server-driven; no local simulation

    # ── Draw ──────────────────────────────────────────────────────────────────

    def pre_draw(self):
        self.stdscr.clear()
        try:
            for i, line in enumerate(self.title):
                self.stdscr.addstr(i, 0, line,
                                   ptk.color_pair(ptk.COLOR_GREEN) | ptk.A_BOLD)
        except Exception:
            pass

    def draw(self):
        self._draw_info_panel()
        self._draw_arena()
        self._draw_death_messages()

    def _draw_info_panel(self):
        """Draw scores just below the title — ships can fly over this text."""
        try:
            y = len(TITLE)
            x = 2
            self.stdscr.addstr(y, x, 'Slot  Player          Score   Status',
                               ptk.color_pair(ptk.COLOR_CYAN) | ptk.A_BOLD)
            for i, p in enumerate(self._players):
                slot = p.get('slot', 0)
                name = p.get('name', '?')[:14]
                score = p.get('score', 0)
                alive = p.get('alive', True)
                is_me = slot == self.my_slot
                color = SLOT_COLORS[slot % len(SLOT_COLORS)]
                status = 'operational' if alive else '  destroyed'
                tag = '(you)' if is_me else '     '
                line = f'  {slot+1}   {name:<14}  {score:>6}  {status}  {tag}'
                attr = (ptk.color_pair(color) | ptk.A_BOLD) if is_me else ptk.color_pair(color)
                try:
                    self.stdscr.addstr(y + 1 + i, x, line, attr)
                except Exception:
                    pass
        except Exception:
            pass

    def _draw_arena(self):
        """Draw the play arena: borders (bottom + right only), stars, ships."""
        import time as _time

        # Draw border — bottom wall and right wall only (no top/left, matching Star Ship)
        try:
            block = glyph('BLOCK')
        except Exception:
            block = '#'

        arena_w = self.arena_width
        arena_h = self.arena_height

        try:
            # Bottom wall
            for rx in range(arena_w + 1):
                self.stdscr.addch(arena_h, rx, block,
                                  ptk.color_pair(ptk.COLOR_BLUE))
            # Right wall
            for ry in range(arena_h + 1):
                self.stdscr.addch(ry, arena_w, block,
                                  ptk.color_pair(ptk.COLOR_BLUE))
        except Exception:
            pass

        # Draw stars — positions are absolute (0-based arena coords)
        for star in self._stars:
            row = star.get('row', 0)
            col = star.get('col', 0)
            try:
                self.stdscr.addch(row, col, '*',
                                  ptk.color_pair(ptk.COLOR_YELLOW) | ptk.A_BOLD)
            except Exception:
                pass

        # Draw special star
        sp = self._special_star
        if sp:
            try:
                sym = glyph('CIRCLE_FILLED')
            except Exception:
                sym = '*'
            try:
                self.stdscr.addch(sp.get('row', 0), sp.get('col', 0), sym,
                                  ptk.color_pair(ptk.COLOR_MAGENTA) | ptk.A_BOLD)
            except Exception:
                pass

        # Draw ships — absolute arena coords, no offset
        try:
            sym_head = glyph('CIRCLE_FILLED')
        except Exception:
            sym_head = 'O'
        try:
            sym_body = glyph('CIRCLE_FILLED')
        except Exception:
            sym_body = 'o'

        for p in self._players:
            if not p.get('alive', True):
                continue
            slot = p.get('slot', 0)
            ship = p.get('ship', [])
            color = SLOT_COLORS[slot % len(SLOT_COLORS)]
            is_me = slot == self.my_slot
            for i, cell in enumerate(ship):
                row = cell.get('row', 0) if isinstance(cell, dict) else cell[0]
                col = cell.get('col', 0) if isinstance(cell, dict) else cell[1]
                sym = sym_head if i == 0 else sym_body
                attr = ptk.color_pair(color) | (ptk.A_BOLD if i == 0 or is_me else ptk.A_NORMAL)
                try:
                    self.stdscr.addch(row, col, sym, attr)
                except Exception:
                    pass

    def _draw_death_messages(self):
        import time as _time
        now = _time.time()
        active = [(s, c, u) for s, c, u in self._player_died_msgs if now < u]
        self._player_died_msgs = active
        for i, (slot, cause, _) in enumerate(active):
            player = next((p for p in self._players if p.get('slot') == slot), {})
            name = player.get('name', f'Slot {slot+1}')
            msg = f'{name} died ({cause})'
            try:
                self.stdscr.addstr(
                    len(TITLE) + 1 + len(self._players) + 2 + i, 2,
                    msg[:self.width - 4],
                    ptk.color_pair(ptk.COLOR_RED),
                )
            except Exception:
                pass


def main(stdscr):
    init_ptk(stdscr)
    # Multiplayer games need socket client — show message if run directly
    try:
        stdscr.addstr(0, 0, 'Star Ship 2 is a multiplayer game. Use: clia mp',
                      ptk.color_pair(ptk.COLOR_YELLOW) | ptk.A_BOLD)
        stdscr.addstr(1, 0, 'Press any key to exit.')
        stdscr.refresh()
        stdscr.nodelay(False)
        stdscr.getch()
    except Exception:
        pass


if __name__ == '__main__':
    try:
        ptk.wrapper(main)
    except KeyboardInterrupt:
        try:
            ptk.endwin()
        except Exception:
            pass
