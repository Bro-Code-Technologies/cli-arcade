"""
games/kernel_kings/game.py  —  Kernel Kings: 2-player turn-based multiplayer
"""
from game_classes import ptk
import os
import sys
import time

try:
    this_dir = os.path.dirname(__file__)
    project_root = os.path.abspath(os.path.join(this_dir, '..', '..'))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
except Exception:
    project_root = None

from game_classes.highscores import HighScores
from game_classes.multiplayer_base import MultiplayerGameBase, is_enter_key
from game_classes.tools import init_ptk, glyph

IS_MULTIPLAYER = True

# TITLE = [
#   "██ ▄█▀ ▄▄▄▄▄ ▄▄▄▄▄ ▄▄  ▄▄ ▄▄▄▄▄ ▄▄      ██ ▄█▀ ▄▄ ▄▄  ▄▄  ▄▄▄▄  ▄▄▄▄", 
#   "████   ██▄▄  ██▄██ ███▄██ ██▄▄  ██      ████   ██ ███▄██ ██ ▄▄ ███▄▄", 
#   "██ ▀█▄ ██▄▄▄ ██ █▄ ██ ▀██ ██▄▄▄ ██▄▄▄   ██ ▀█▄ ██ ██ ▀██ ▀███▀ ▄▄██▀", 
# ]

    
TITLE = [                                                                     
" ▄▄▄▄   ▄▄▄                       ▄▄     ▄▄▄▄   ▄▄▄                     ",
"█▀ ██  ██                          ██   █▀ ██  ██                       ",
"   ██ ██          ▄    ▄           ██      ██ ██    ▀▀ ▄        ▄▄      ",
"   █████    ▄█▀█▄ ████▄████▄ ▄█▀█▄ ██      █████    ██ ████▄ ▄████ ▄██▀█",
"   ██ ██▄   ██▄█▀ ██   ██ ██ ██▄█▀ ██      ██ ██▄   ██ ██ ██ ██ ██ ▀███▄",
" ▀██▀  ▀██▄▄▀█▄▄▄▄█▀  ▄██ ▀█▄▀█▄▄▄▄██    ▀██▀  ▀██▄▄██▄██ ▀█▄▀█████▄▄██▀",
"                                                                ██      ",
"                                                              ▀▀▀       ",
]

DESCRIPTION = """2-player turn-based Kernel Kings in the terminal!
Classic American/English rules — diagonal slides, mandatory jumps, king promotion.
Press Enter to go to the lobby and find an opponent."""

MIN_COLS = 90
MIN_ROWS = 34

# Board rendering constants
CELL_W = 5    # Characters wide per cell (was 3)
CELL_H = 3    # Lines tall per cell (was 2)

BOARD_OFFSET_X = 4    # Left padding for the board
BOARD_OFFSET_Y = 6    # Top padding (after title + gap)

INFO_PANEL_X = BOARD_OFFSET_X + 8 * CELL_W + 6   # To the right of the board

# Colors for the two players
PLAYER_COLORS = [ptk.COLOR_RED, ptk.COLOR_BLUE]


def _dark_square(row, col):
    return (row + col) % 2 == 1


class Game(MultiplayerGameBase):
    def __init__(self, stdscr, player_name='Player', socket_client=None, game_data=None):
        self.title = TITLE

        self.highscores = HighScores('kernel_kings', {
            'wins':     {'player': 'Player', 'value': 0},
            'captures': {'player': 'Player', 'value': 0},
        })

        game_data = game_data or {}
        super().__init__(stdscr, player_name, socket_client, game_data, tick=0.10)

        self.init_scores([['wins', 0], ['captures', 0]])

        # Board state — updated by on_game_state
        self._board = None          # 8×8 list of lists
        self._turn: int = 0         # 0=red, 1=blue
        self._players_info = []
        self._must_jump = None      # {row, col}
        self._turn_deadline: float = 0.0
        self._captures_red = 0
        self._captures_blue = 0

        # Cursor / selection (input system)
        self.cursor = [3, 3]        # [row, col]
        self.selected = None        # [row, col] or None
        self.legal_moves = []       # [(row, col)]
        self.jump_targets = []      # [(row, col)] — subset of legal_moves that are jumps

        # Feedback messages
        self._flash_msg = ''
        self._flash_until = 0.0

        # Cache board dimensions
        self._cell_h = CELL_H
        self._cell_w = CELL_W
        self._board_off_y = BOARD_OFFSET_Y + len(TITLE) - 4

    # ── Network callbacks ──────────────────────────────────────────────────────

    def on_game_state(self, state):
        self._board = state.get('board', self._board)
        turn_raw = state.get('turn', 0)
        self._turn = int(turn_raw) if turn_raw is not None else 0
        self._players_info = state.get('players', self._players_info)
        mj = state.get('mustJump')
        self._must_jump = mj  # dict with row/col or None
        self._turn_deadline = state.get('turnDeadline', 0) / 1000.0
        self._captures_red = state.get('capturedRed', 0)
        self._captures_blue = state.get('capturedBlue', 0)

        # Auto-select must-jump piece
        if self._must_jump and self._is_my_turn():
            self.selected = [self._must_jump['row'], self._must_jump['col']]
            self._compute_legal_moves()

    def on_game_over(self, results):
        super().on_game_over(results)
        winner = results.get('winner')
        if winner == self.my_slot:
            self.scores['wins'] = int(self.scores.get('wins', 0)) + 1
        my_player = next((p for p in self._players_info if p.get('slot') == self.my_slot), {})
        captures = my_player.get('captures', 0)
        if captures > int(self.scores.get('captures', 0)):
            self.scores['captures'] = captures
        self.update_high_scores()

    def on_invalid_move(self, data):
        self._flash_msg = data.get('reason', 'Invalid move')
        self._flash_until = time.time() + 2.5
        # Deselect on invalid
        self.selected = None
        self.legal_moves = []
        self.jump_targets = []

    def step(self, now):
        pass  # Server-driven

    # ── Input system ──────────────────────────────────────────────────────────

    def movement(self, ch):
        if not self._is_my_turn():
            return  # Not our turn; cursor navigation still allowed below

        flipped = self.my_slot == 0
        if ch in (ptk.KEY_UP, ord('w')):
            if flipped:
                self.cursor[0] = min(7, self.cursor[0] + 1)
            else:
                self.cursor[0] = max(0, self.cursor[0] - 1)
        elif ch in (ptk.KEY_DOWN, ord('s')):
            if flipped:
                self.cursor[0] = max(0, self.cursor[0] - 1)
            else:
                self.cursor[0] = min(7, self.cursor[0] + 1)
        elif ch in (ptk.KEY_LEFT, ord('a')):
            self.cursor[1] = max(0, self.cursor[1] - 1)
        elif ch in (ptk.KEY_RIGHT, ord('d')):
            self.cursor[1] = min(7, self.cursor[1] + 1)
        elif ch == 9:  # Tab — cycle through own pieces with legal moves
            self._cycle_pieces()
        elif is_enter_key(ch):
            self._handle_enter()
        elif ch in (27, ptk.KEY_BACKSPACE, 127, 8):
            # ESC handled in run() for quit, but if we have selection, deselect
            if self.selected is not None:
                self.selected = None
                self.legal_moves = []
                self.jump_targets = []

    def _is_my_turn(self):
        return self._turn == self.my_slot

    def _handle_enter(self):
        crow, ccol = self.cursor

        if self.selected is None:
            # Try to select a piece
            piece = self._get_piece(crow, ccol)
            if piece and piece.get('owner') == self.my_slot:
                # If mustJump, only allow selecting the must-jump piece
                if self._must_jump:
                    if crow != self._must_jump.get('row') or ccol != self._must_jump.get('col'):
                        self._flash('Must continue jumping with highlighted piece!')
                        return
                self.selected = [crow, ccol]
                self._compute_legal_moves()
                if not self.legal_moves:
                    self._flash('No legal moves from this piece.')
                    self.selected = None
        else:
            # Check if cursor is on a legal target
            if [crow, ccol] in self.legal_moves:
                # Submit move
                self.send_move({
                    'from': {'row': self.selected[0], 'col': self.selected[1]},
                    'to':   {'row': crow, 'col': ccol},
                })
                self.selected = None
                self.legal_moves = []
                self.jump_targets = []
            elif [crow, ccol] == self.selected:
                # Clicking own selected piece deselects
                self.selected = None
                self.legal_moves = []
                self.jump_targets = []
            else:
                piece = self._get_piece(crow, ccol)
                if piece and piece.get('owner') == self.my_slot:
                    # Switch selection to another piece
                    self.selected = [crow, ccol]
                    self._compute_legal_moves()
                else:
                    self._flash('Not a legal target.')

    def _cycle_pieces(self):
        """Tab: cycle cursor through own pieces that have legal moves."""
        if not self._board or not self._is_my_turn():
            return
        candidates = []
        for r in range(8):
            for c in range(8):
                cell = self._get_piece(r, c)
                if cell and cell.get('owner') == self.my_slot:
                    moves = self._compute_legal_moves_for(r, c)
                    if moves:
                        candidates.append([r, c])
        if not candidates:
            return
        try:
            cur_idx = candidates.index(self.cursor)
            next_idx = (cur_idx + 1) % len(candidates)
        except ValueError:
            next_idx = 0
        self.cursor = candidates[next_idx]
        self.selected = self.cursor[:]
        self._compute_legal_moves()

    def _compute_legal_moves(self):
        """Compute legal_moves and jump_targets for self.selected piece."""
        if not self.selected or not self._board:
            self.legal_moves = []
            self.jump_targets = []
            return
        row, col = self.selected
        moves = self._compute_legal_moves_for(row, col)
        self.legal_moves = [[m['to']['row'], m['to']['col']] for m in moves]
        self.jump_targets = [[m['to']['row'], m['to']['col']] for m in moves if m.get('jumped')]

    def _compute_legal_moves_for(self, row, col):
        """Client-side move computation for a specific piece."""
        if not self._board:
            return []
        piece = self._get_piece(row, col)
        if not piece:
            return []
        owner = piece.get('owner')
        is_king = piece.get('king', False)

        dirs_slide = [[1, -1], [1, 1]] if owner == 0 else [[-1, -1], [-1, 1]]
        dirs_all = [[1, -1], [1, 1], [-1, -1], [-1, 1]]
        dirs = dirs_all if is_king else dirs_slide

        jumps = []
        slides = []
        for dr, dc in dirs:
            nr, nc = row + dr, col + dc
            jr, jc = row + dr * 2, col + dc * 2
            if 0 <= nr < 8 and 0 <= nc < 8:
                cell = self._get_piece(nr, nc)
                if cell is None:
                    slides.append({'from': {'row': row, 'col': col},
                                   'to': {'row': nr, 'col': nc},
                                   'jumped': None})
                if cell and cell.get('owner') != owner:
                    if 0 <= jr < 8 and 0 <= jc < 8 and self._get_piece(jr, jc) is None:
                        jumps.append({'from': {'row': row, 'col': col},
                                      'to': {'row': jr, 'col': jc},
                                      'jumped': {'row': nr, 'col': nc}})

        # Check if any piece of this owner has jumps available (mandatory)
        all_jumps = []
        for r in range(8):
            for c in range(8):
                pc = self._get_piece(r, c)
                if pc and pc.get('owner') == owner:
                    for dr, dc in dirs_all if (pc.get('king') or is_king) else (dirs_all):
                        nr2, nc2 = r + dr, c + dc
                        jr2, jc2 = r + dr * 2, c + dc * 2
                        if 0 <= nr2 < 8 and 0 <= nc2 < 8:
                            over = self._get_piece(nr2, nc2)
                            if over and over.get('owner') != owner:
                                if 0 <= jr2 < 8 and 0 <= jc2 < 8 and self._get_piece(jr2, jc2) is None:
                                    all_jumps.append(True)

        if all_jumps:
            return jumps  # mandatory jumps
        return jumps if jumps else slides

    def _get_piece(self, row, col):
        if not self._board:
            return None
        try:
            return self._board[row][col]
        except (IndexError, TypeError):
            return None

    def _compute_all_legal_for_owner(self, owner):
        """Check if any moves exist for an owner (used for legal-move highlights)."""
        if not self._board:
            return []
        moves = []
        for r in range(8):
            for c in range(8):
                pc = self._get_piece(r, c)
                if pc and pc.get('owner') == owner:
                    moves.extend(self._compute_legal_moves_for(r, c))
        return moves

    def _flash(self, msg, duration=2.5):
        self._flash_msg = msg
        self._flash_until = time.time() + duration

    # ── Draw ──────────────────────────────────────────────────────────────────

    def pre_draw(self):
        self.stdscr.clear()
        try:
            for i, line in enumerate(self.title):
                self.stdscr.addstr(i, 0, line, ptk.color_pair(ptk.COLOR_BLUE) | ptk.A_BOLD)
        except Exception:
            pass

    def draw(self):
        self._draw_board()
        self._draw_info_panel()
        self._draw_flash()

    def _disp_row(self, board_row: int) -> int:
        """Map a board row to a visual row.
        Slot 0 (host) sees the board flipped so their pieces start at the bottom.
        Slot 1 (guest) sees the standard orientation.
        """
        return 7 - board_row if self.my_slot == 0 else board_row

    def _draw_board(self):
        if not self._board:
            try:
                self.stdscr.addstr(self._board_off_y, BOARD_OFFSET_X,
                                   'Waiting for game state...',
                                   ptk.color_pair(ptk.COLOR_WHITE))
            except Exception:
                pass
            return

        off_y = self._board_off_y
        off_x = BOARD_OFFSET_X
        cw = self._cell_w
        ch = self._cell_h

        for row in range(8):
            for col in range(8):
                dark = _dark_square(row, col)
                piece = self._get_piece(row, col)
                is_cursor = self.cursor == [row, col]
                is_selected = self.selected == [row, col]
                is_legal = [row, col] in self.legal_moves
                is_jump = [row, col] in self.jump_targets
                must_j = (self._must_jump and
                          self._must_jump.get('row') == row and
                          self._must_jump.get('col') == col)

                cell_y = off_y + self._disp_row(row) * ch
                cell_x = off_x + col * cw

                # Background style
                if is_cursor and is_selected:
                    bg_attr = ptk.color_pair(ptk.COLOR_CYAN) | ptk.A_REVERSE
                elif is_cursor:
                    bg_attr = ptk.A_REVERSE
                elif is_jump:
                    bg_attr = ptk.color_pair(ptk.COLOR_YELLOW) | ptk.A_REVERSE
                elif is_legal:
                    bg_attr = ptk.color_pair(ptk.COLOR_GREEN) | ptk.A_REVERSE
                elif must_j and self._is_my_turn():
                    bg_attr = ptk.color_pair(ptk.COLOR_MAGENTA) | ptk.A_REVERSE
                elif dark and not piece:
                    bg_attr = ptk.A_NORMAL
                elif dark:
                    bg_attr = ptk.A_NORMAL
                else:
                    bg_attr = ptk.color_pair(ptk.COLOR_RED) | ptk.A_REVERSE

                # Fill cell background
                for line_off in range(ch):
                    try:
                        self.stdscr.addstr(cell_y + line_off, cell_x,
                                           ' ' * cw, bg_attr)
                    except Exception:
                        pass

                # Draw piece centered in the cell
                if piece:
                    owner = piece.get('owner', 0)
                    king = piece.get('king', False)
                    color = PLAYER_COLORS[owner % len(PLAYER_COLORS)]
                    # Kings: filled circle, others: hollow circle
                    try:
                        sym = glyph('CIRCLE_FILLED') if king else glyph('CIRCLE')
                    except Exception:
                        sym = 'O'
                    piece_attr = ptk.color_pair(color) | ptk.A_BOLD
                    center_x = cell_x + cw // 2
                    center_y = cell_y + ch // 2
                    if king:
                        # King: ◉ centered
                        king_str = sym
                        kx = cell_x + (cw - len(king_str)) // 2
                        try:
                            self.stdscr.addstr(center_y, kx, king_str, piece_attr)
                        except Exception:
                            pass
                    else:
                        try:
                            self.stdscr.addch(center_y, center_x, sym[0], piece_attr)
                        except Exception:
                            pass

    def _draw_info_panel(self):
        off_y = self._board_off_y
        px = INFO_PANEL_X
        now = time.time()

        try:
            self.stdscr.addstr(off_y, px, 'Players:',
                               ptk.color_pair(ptk.COLOR_CYAN) | ptk.A_BOLD)
        except Exception:
            pass

        for i, p in enumerate(self._players_info):
            slot = p.get('slot', i)
            name = p.get('name', f'Slot {slot+1}')
            caps = p.get('captures', 0)
            color = PLAYER_COLORS[slot % len(PLAYER_COLORS)]
            is_me = slot == self.my_slot
            is_turn = slot == self._turn
            turn_mark = '►' if is_turn else ' '
            line = f'{turn_mark} {name}'
            attr = ptk.color_pair(color) | (ptk.A_BOLD if is_me or is_turn else ptk.A_NORMAL)
            try:
                self.stdscr.addstr(off_y + 1 + i, px, line[:30], attr)
            except Exception:
                pass

        # Turn indicator
        turn_player = next((p for p in self._players_info if p.get('slot') == self._turn), {})
        turn_label = turn_player.get('name', f'Slot {self._turn+1}')
        my_turn = self._is_my_turn()
        turn_str = 'YOUR TURN!' if my_turn else f"{turn_label}'s turn"
        turn_color = ptk.COLOR_GREEN if my_turn else ptk.COLOR_WHITE
        try:
            self.stdscr.addstr(off_y + 4, px, turn_str,
                               ptk.color_pair(turn_color) | ptk.A_BOLD)
        except Exception:
            pass

        # Timer countdown
        if self._turn_deadline > 0:
            remaining = max(0, int(self._turn_deadline - now))
            timer_color = ptk.COLOR_RED if remaining < 15 else ptk.COLOR_WHITE
            try:
                self.stdscr.addstr(off_y + 5, px, f'Time: {remaining:>3}s',
                                   ptk.color_pair(timer_color))
            except Exception:
                pass

        # Waiting indicator
        if not my_turn:
            try:
                self.stdscr.addstr(off_y + 7, px, 'Waiting for opponent...',
                                   ptk.color_pair(ptk.COLOR_WHITE) | ptk.A_DIM)
            except Exception:
                pass

        # Key hints
        hints = [
            'Arrow/WASD: move cursor',
            'Enter: select/move',
            'Tab: next movable piece',
            'ESC: quit',
        ]
        for i, hint in enumerate(hints):
            try:
                self.stdscr.addstr(off_y + 9 + i, px, hint,
                                   ptk.color_pair(ptk.COLOR_WHITE) | ptk.A_DIM)
            except Exception:
                pass

    def _draw_flash(self):
        if not self._flash_msg or time.time() >= self._flash_until:
            return
        try:
            _, rows = self.stdscr.getmaxyx()
            self.stdscr.addstr(rows - 2, 2,
                               f'{self._flash_msg}'[:self.width - 4],
                               ptk.color_pair(ptk.COLOR_RED) | ptk.A_BOLD)
        except Exception:
            pass


def main(stdscr):
    init_ptk(stdscr)
    try:
        stdscr.addstr(0, 0, 'Kernel Kings is a multiplayer game. Use: clia mp',
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
