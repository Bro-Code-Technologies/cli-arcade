"""
game_classes/multiplayer_base.py

MultiplayerGameBase — extends GameBase with a network-aware game loop.

Subclasses implement:
    on_game_state(state)   — called when game:state arrives; update local render state
    on_game_over(results)  — called when game:over arrives; show results
    draw()                 — render the current state
    movement(ch)           — handle key input (usually emits game:input / game:move)
    step(now)              — usually a no-op; server drives state

The base handles:
    - Socket polling every frame
    - Disconnect overlay with countdown
    - Common game-over screen with rankings (press Enter→lobby, ESC→quit)
    - send_input(data) helper that emits game:input
"""

import time
from game_classes import ptk
from game_classes.game_base import GameBase
from game_classes.tools import get_terminal_size


class MultiplayerGameBase(GameBase):

    def __init__(self, stdscr, player_name, socket_client, game_data, tick=0.05):
        """
        Parameters
        ----------
        stdscr        : curses/ptk screen
        player_name   : local player's display name
        socket_client : connected SocketClient instance
        game_data     : dict received with game:start event
            {gameType, mySlot, players, arenaWidth, arenaHeight, seed}
        tick          : frame interval (seconds); real-time games typically 0.05
        """
        self.game_data = game_data
        self.socket_client = socket_client
        self.my_slot = game_data.get('mySlot', 0)
        self.all_players = game_data.get('players', [])
        self.arena_width = game_data.get('arenaWidth', 60)
        self.arena_height = game_data.get('arenaHeight', 18)

        # Report our terminal size to the server (for future reconnect use)
        try:
            rows, cols = stdscr.getmaxyx()
            socket_client.emit('game:report_size', {'cols': cols, 'rows': rows})
        except Exception:
            pass

        # Game-over state: set by on_game_over
        self._mp_over = False
        self._mp_results = None        # raw results payload
        self._mp_over_time = None      # when game over was received

        # Disconnect overlay
        self._disconnect_msg: str = ''
        self._disconnect_until: float = 0.0

        # Initialize HighScores *before* super().__init__() — subclasses must
        # set self.highscores before calling this __init__.
        super().__init__(stdscr, player_name, tick, ptk.COLOR_CYAN)

    # ── Public helpers ─────────────────────────────────────────────────────────

    def send_input(self, data):
        """Convenience: emit game:input to the server."""
        self.socket_client.emit('game:input', data)

    def send_move(self, data):
        """Convenience: emit game:move to the server."""
        self.socket_client.emit('game:move', data)

    # ── Overridable network callbacks ──────────────────────────────────────────

    def on_game_state(self, state):
        """Called with the decoded state dict every time game:state arrives."""
        pass

    def on_game_over(self, results):
        """Called with the decoded results dict when game:over arrives."""
        self._mp_results = results
        self._mp_over = True
        self._mp_over_time = time.time()

    def on_player_died(self, data):
        """Optional: called with game:player_died payload."""
        pass

    def on_invalid_move(self, data):
        """Optional: called with game:invalid_move payload."""
        pass

    # ── Internal: poll + dispatch ──────────────────────────────────────────────

    def _poll_socket(self):
        for event, data in self.socket_client.poll():
            if event == 'game:state':
                self.on_game_state(data)
            elif event == 'game:over':
                self.on_game_over(data)
            elif event == 'game:player_died':
                self.on_player_died(data)
            elif event == 'game:invalid_move':
                self.on_invalid_move(data)
            elif event == 'lobby:dissolved':
                reason = data.get('reason', 'Lobby dissolved') if isinstance(data, dict) else 'Lobby dissolved'
                self._disconnect_msg = reason
                self._disconnect_until = time.time() + 5
                self._mp_over = True
                self._mp_over_time = time.time()
            elif event == '_disconnected':
                self._disconnect_msg = 'Lost connection to server'
                self._disconnect_until = time.time() + 30

    # ── Overridden game loop ───────────────────────────────────────────────────

    def run(self):
        """
        Multiplayer game loop — polls socket every frame, skips step() when
        the server drives state, draws game-over screen after game ends.
        """
        from game_classes.tools import init_ptk
        init_ptk(self.stdscr)

        last = time.time()
        while True:
            now = time.time()

            # Poll socket first
            self._poll_socket()

            # Input
            ch = self.stdscr.getch()
            if not self._mp_over:
                if ch == 27:        # ESC → leave
                    break
                elif ch != -1:
                    self.events(ch)
            else:
                # Game over: Enter → return to lobby, ESC → quit
                if is_enter_key(ch) or ch == 27:
                    break

            # Step (no-op in most MP games; server drives state)
            if now - last > self.tick and not self._mp_over:
                self.step(now)
                last = now

            # Draw
            self.pre_draw()
            self.draw()
            self._draw_disconnect_overlay()
            if self._mp_over:
                self._draw_game_over_screen()
            self.stdscr.refresh()

            time.sleep(0.01)

        # Notify server the player is leaving (cleans up lobby / stops engine)
        try:
            self.socket_client.emit('lobby:leave')
        except Exception:
            pass
        self.save_scores_on_exit()

    def events(self, ch):
        """In multiplayer, ESC is handled in run(); forward others to movement()."""
        if ch != -1 and not self._mp_over:
            self.movement(ch)
        return False

    # ── Overlays ───────────────────────────────────────────────────────────────

    def _draw_disconnect_overlay(self):
        if not self._disconnect_msg:
            return
        if time.time() > self._disconnect_until:
            self._disconnect_msg = ''
            return
        try:
            remaining = max(0, int(self._disconnect_until - time.time()))
            msg = f'  {self._disconnect_msg} (timeout in {remaining}s)  '
            py = self.height // 2
            px = max(0, (self.width - len(msg)) // 2)
            self.stdscr.addstr(py, px, msg,
                               ptk.color_pair(ptk.COLOR_RED) | ptk.A_BOLD)
        except Exception:
            pass

    def _draw_game_over_screen(self):
        """Render a unified game-over / rankings overlay."""
        try:
            results = self._mp_results or {}
            rankings = results.get('rankings', [])

            lines = ['  GAME OVER  ']

            # Star Ship 2 style: flat rankings list
            if rankings:
                lines.append('')
                for i, r in enumerate(rankings):
                    name = r.get('name', '?')[:14]
                    score = r.get('score', 0)
                    alive = r.get('alive', False)
                    status = 'alive' if alive else 'dead'
                    lines.append(f'  #{i + 1}  {name:<14}  {score:>6}  ({status})')

            # Kernel Kings style: winner / reason
            winner = results.get('winner')
            reason = results.get('reason', '')
            if winner is not None or reason:
                players = results.get('players', [])
                winner_name = next((p.get('name', '?') for p in players if p.get('slot') == winner), 'Unknown')
                if winner is None:
                    lines.append('  Draw!')
                elif winner == self.my_slot:
                    lines.append(f'  You Win!')
                else:
                    lines.append(f'  {winner_name} wins')
                if reason:
                    lines.append(f'  ({reason})')
                lines.append('')
                for p in players:
                    lines.append(f'  Slot {p.get("slot", "?")+1}  {p.get("name", "?"):<14}  Captures: {p.get("captures", 0)}')

            lines.append('')
            lines.append('  [Enter] Return to Lobby    [ESC] Quit  ')

            box_w = max((len(l) for l in lines), default=20) + 4
            box_h = len(lines) + 2
            start_y = max(0, (self.height - box_h) // 2)
            start_x = max(0, (self.width - box_w) // 2)

            # Draw box
            for row_off in range(box_h):
                y = start_y + row_off
                attr = ptk.color_pair(ptk.COLOR_YELLOW) | ptk.A_BOLD
                if row_off == 0 or row_off == box_h - 1:
                    try:
                        self.stdscr.addstr(y, start_x, '+' + '-' * (box_w - 2) + '+', attr)
                    except Exception:
                        pass
                else:
                    line = lines[row_off - 1] if row_off - 1 < len(lines) else ''
                    padded = ('|' + line.ljust(box_w - 2) + '|')[:box_w]
                    try:
                        self.stdscr.addstr(y, start_x, padded, attr)
                    except Exception:
                        pass
        except Exception:
            pass


def is_enter_key(ch):
    try:
        enter_vals = {10, 13, getattr(ptk, 'KEY_ENTER', -1), 343, 459}
    except Exception:
        enter_vals = {10, 13}
    return ch in enter_vals
