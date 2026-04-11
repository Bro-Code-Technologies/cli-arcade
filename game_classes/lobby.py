"""
game_classes/lobby.py

Terminal UI for the multiplayer lobby system.
Three screens: Lobby Browser, Create Lobby, Waiting Room.
All rendering uses ptk.py primitives.
"""

import shutil
import time
from game_classes import ptk
from game_classes.tools import is_enter_key, glyph

# ── Constants ─────────────────────────────────────────────────────────────────

GAME_TYPES = ['star_ship_2', 'kernel_kings']
GAME_TYPE_LABELS = {
    'star_ship_2': 'Star Ship 2  (1-4 players, real-time)',
    'kernel_kings': 'Kernel Kings (1-2 players, turn-based)',
}

# Per-game max player options; index 0 is the default on open
GAME_MAX_PLAYERS = {
    'star_ship_2': [1, 2, 3, 4],
    'kernel_kings': [1, 2],
}

# Tooltip shown when 1-player option is selected
GAME_SINGLE_PLAYER_NOTE = {
    'star_ship_2': '1 player solo',
    'kernel_kings': '1 player vs AI',
}

LOBBY_TIMEOUT_SECONDS = 5 * 60   # must match server LOBBY_TIMEOUT_MS

# Minimum terminal dimensions required per game (cols, rows)
GAME_MIN_SIZES = {
    'star_ship_2':  (80, 22),
    'kernel_kings': (90, 34),
}

REFRESH_INTERVAL = 3.0   # seconds between automatic lobby list refreshes


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_size(stdscr):
    try:
        rows, cols = stdscr.getmaxyx()
    except Exception:
        try:
            ts = shutil.get_terminal_size()
            cols, rows = ts.columns, ts.lines
        except Exception:
            cols, rows = 80, 24
    return cols, rows


def _center_str(stdscr, row, text, attr=ptk.A_NORMAL):
    try:
        cols, _ = _get_size(stdscr)
        x = max(0, (cols - len(text)) // 2)
        stdscr.addstr(row, x, text, attr)
    except Exception:
        pass


def _draw_header(stdscr, title):
    try:
        cols, _ = _get_size(stdscr)
        header = f' CLI ARCADE  ·  {title} '
        stdscr.addstr(0, 0, header[:cols - 1], ptk.color_pair(ptk.COLOR_CYAN) | ptk.A_BOLD)
    except Exception:
        pass


def _draw_footer(stdscr, hint):
    try:
        cols, rows = _get_size(stdscr)
        footer = hint[:cols - 1]
        try:
            stdscr.addstr(rows - 1, 0, footer, ptk.color_pair(ptk.COLOR_WHITE))
        except Exception:
            pass
    except Exception:
        pass


def _mask_char(ch):
    """Render characters as '*' for password input."""
    return '*'


# ── Screen: Lobby Browser ─────────────────────────────────────────────────────

def lobby_browser(stdscr, socket_client, player_name):
    """
    Display the lobby list.
    Returns a dict describing the next action:
       {'action': 'join', 'lobby': {...}}
       {'action': 'create'}
       {'action': 'join_code'}
       {'action': 'quit'}
    """
    lobbies = []
    sel = 0
    last_refresh = 0.0
    error_msg = ''
    error_until = 0.0

    stdscr.nodelay(True)
    stdscr.timeout(100)

    while True:
        now = time.time()
        cols, rows = _get_size(stdscr)

        # Auto-refresh lobby list
        if now - last_refresh >= REFRESH_INTERVAL:
            socket_client.emit('lobby:list')
            last_refresh = now

        # Poll events
        for event, data in socket_client.poll():
            if event == 'lobby:list':
                if isinstance(data, list):
                    lobbies = data
                elif isinstance(data, dict) and 'lobbies' in data:
                    lobbies = data['lobbies']
                if sel >= len(lobbies) and len(lobbies) > 0:
                    sel = len(lobbies) - 1
            elif event == 'lobby:error':
                error_msg = data.get('message', 'Unknown error')
                error_until = now + 3.0
            elif event == '_disconnected':
                return {'action': 'quit', 'reason': 'Disconnected from server.'}

        # Draw
        stdscr.erase()
        _draw_header(stdscr, 'MULTIPLAYER LOBBY')

        list_start = 2
        list_end = rows - 3
        avail = max(1, list_end - list_start)

        # Column headers
        try:
            header_row = list_start
            stdscr.addstr(
                header_row, 2,
                f"{'Game':<22} {'Players':<10} {'Host':<16} {'Status':<8}",
                ptk.color_pair(ptk.COLOR_YELLOW) | ptk.A_BOLD,
            )
        except Exception:
            pass

        list_start += 1
        avail = max(1, list_end - list_start)

        # Clamp top to keep sel visible
        top = max(0, sel - avail + 1) if sel >= avail else 0

        if not lobbies:
            try:
                stdscr.addstr(list_start + 1, 4, 'No open lobbies. Press C to create one.',
                              ptk.color_pair(ptk.COLOR_WHITE))
            except Exception:
                pass
        else:
            for vis_i in range(min(avail, len(lobbies))):
                idx = top + vis_i
                if idx >= len(lobbies):
                    break
                lobby = lobbies[idx]
                is_sel = idx == sel
                game_label = lobby.get('gameType', '?').replace('_', ' ').title()[:20]
                players = f"{lobby.get('playerCount', '?')}/{lobby.get('maxPlayers', '?')}"
                host = lobby.get('hostName', 'Unknown')[:14]
                status = lobby.get('status', '?')[:8]
                lock = ''
                if lobby.get('hasPassword'):
                    try:
                        lock = glyph('BLOCK') + ' '
                    except Exception:
                        lock = '[P] '
                line = f"{lock}{game_label:<22} {players:<10} {host:<16} {status:<8}"
                attr = ptk.A_REVERSE if is_sel else ptk.A_NORMAL
                try:
                    stdscr.addstr(list_start + vis_i, 2, line[:cols - 4],
                                  ptk.color_pair(ptk.COLOR_CYAN) | attr)
                except Exception:
                    pass

        # Error banner
        if error_msg and now < error_until:
            try:
                stdscr.addstr(rows - 2, 2, f'Error: {error_msg}'[:cols - 4],
                              ptk.color_pair(ptk.COLOR_RED) | ptk.A_BOLD)
            except Exception:
                pass

        _draw_footer(stdscr,
                     '[↑/↓] Navigate  [Enter] Join  [C] Create  [J] Join by code  [ESC] Quit')
        stdscr.refresh()

        ch = stdscr.getch()
        if ch == -1:
            continue
        if ch == ptk.KEY_UP:
            sel = max(0, sel - 1)
        elif ch == ptk.KEY_DOWN:
            sel = min(max(0, len(lobbies) - 1), sel + 1)
        elif is_enter_key(ch) and lobbies:
            chosen = lobbies[sel]
            min_c, min_r = GAME_MIN_SIZES.get(chosen.get('gameType', ''), (0, 0))
            cur_c, cur_r = _get_size(stdscr)
            if cur_c < min_c or cur_r < min_r:
                error_msg = f'Terminal too small for this game. Need {min_c}×{min_r}, have {cur_c}×{cur_r}.'
                error_until = now + 4.0
            else:
                return {'action': 'join', 'lobby': chosen}
        elif ch in (ord('C'), ord('c')):
            return {'action': 'create'}
        elif ch in (ord('J'), ord('j')):
            return {'action': 'join_code'}
        elif ch == 27:
            return {'action': 'quit'}


# ── Screen: Create Lobby ──────────────────────────────────────────────────────

def create_lobby(stdscr, socket_client, player_name):
    """
    Form to create a new lobby.
    Returns: {'action': 'created', 'lobby': data, 'password': password} or {'action': 'cancel'}.
    """
    sel_game = 0
    prev_sel_game = -1          # detect game change to reset max-player selection
    sel_max = 1                 # default to index 1 (2 players) for most games
    password = ''
    field = 0     # 0=game, 1=maxPlayers, 2=password, 3=confirm
    error_msg = ''
    error_until = 0.0
    pw_error_msg = ''
    pw_error_until = 0.0

    stdscr.nodelay(True)
    stdscr.timeout(100)

    while True:
        now = time.time()
        cols, rows = _get_size(stdscr)

        # Sync max-player options when game type changes
        if sel_game != prev_sel_game:
            max_opts = GAME_MAX_PLAYERS.get(GAME_TYPES[sel_game], [2, 3, 4])
            # Keep sel_max at index 1 (2 players) if available, else clamp
            sel_max = min(max(sel_max, 0), len(max_opts) - 1)
            prev_sel_game = sel_game
        max_opts = GAME_MAX_PLAYERS.get(GAME_TYPES[sel_game], [2, 3, 4])
        sel_max = min(sel_max, len(max_opts) - 1)

        for event, data in socket_client.poll():
            if event == 'lobby:created':
                return {'action': 'created', 'lobby': data, 'password': password}
            elif event == 'lobby:error':
                error_msg = data.get('message', 'Error')
                error_until = now + 4.0

        stdscr.erase()
        _draw_header(stdscr, 'CREATE GAME')

        try:
            stdscr.addstr(2, 2, 'Game:', ptk.color_pair(ptk.COLOR_YELLOW) | ptk.A_BOLD)
            for i, gt in enumerate(GAME_TYPES):
                if field == 0:
                    attr = ptk.A_REVERSE if i == sel_game else ptk.A_NORMAL
                else:
                    # When not focused on game field, show selected in green
                    attr = (ptk.color_pair(ptk.COLOR_GREEN) | ptk.A_BOLD) if i == sel_game else ptk.A_NORMAL
                label = GAME_TYPE_LABELS.get(gt, gt)
                try:
                    stdscr.addstr(3 + i, 4, label,
                                  ptk.color_pair(ptk.COLOR_CYAN) | attr)
                except Exception:
                    pass

            max_row = 3 + len(GAME_TYPES) + 1
            stdscr.addstr(max_row, 2, 'Max Players:', ptk.color_pair(ptk.COLOR_YELLOW) | ptk.A_BOLD)
            for i, n in enumerate(max_opts):
                if field == 1:
                    attr = ptk.A_REVERSE if i == sel_max else ptk.A_NORMAL
                else:
                    attr = (ptk.color_pair(ptk.COLOR_GREEN) | ptk.A_BOLD) if i == sel_max else ptk.A_NORMAL
                try:
                    stdscr.addstr(max_row, 16 + i * 4, str(n),
                                  ptk.color_pair(ptk.COLOR_CYAN) | attr)
                except Exception:
                    pass
            # Note when 1-player is selected
            if max_opts[sel_max] == 1:
                note = GAME_SINGLE_PLAYER_NOTE.get(GAME_TYPES[sel_game], '')
                try:
                    stdscr.addstr(max_row + 1, 4, note,
                                  ptk.color_pair(ptk.COLOR_WHITE) | ptk.A_DIM)
                except Exception:
                    pass
                pw_row = max_row + 3
            else:
                pw_row = max_row + 2

            stdscr.addstr(pw_row, 2, 'Password (4-12 alphanumeric, blank=public):',
                          ptk.color_pair(ptk.COLOR_YELLOW) | ptk.A_BOLD)
            pw_attr = ptk.A_REVERSE if field == 2 else ptk.A_NORMAL
            pw_display = (password if password else '') + '_'
            try:
                stdscr.addstr(pw_row, 45, pw_display[:cols - 47],
                              ptk.color_pair(ptk.COLOR_CYAN) | pw_attr)
            except Exception:
                pass
            if pw_error_msg and now < pw_error_until:
                try:
                    stdscr.addstr(pw_row + 1, 4, pw_error_msg[:cols - 8],
                                  ptk.color_pair(ptk.COLOR_RED) | ptk.A_BOLD)
                except Exception:
                    pass
            pw_error_row_offset = 1 if (pw_error_msg and now < pw_error_until) else 0

            # Summary
            summary_row = pw_row + 2 + pw_error_row_offset
            game_name = GAME_TYPE_LABELS.get(GAME_TYPES[sel_game], '?').split('(')[0].strip()
            sel_n = max_opts[sel_max]
            if sel_n == 1:
                players_label = GAME_SINGLE_PLAYER_NOTE.get(GAME_TYPES[sel_game], '1 Player')
            else:
                players_label = f'{sel_n} Players'
            pw_label = password if password else 'Public'
            try:
                stdscr.addstr(summary_row, 2, f'{game_name} | {players_label} | PASS:{pw_label}',
                              ptk.color_pair(ptk.COLOR_WHITE) | ptk.A_BOLD)
            except Exception:
                pass

            confirm_row = summary_row + 2
            confirm_attr = ptk.A_REVERSE if field == 3 else ptk.A_NORMAL
            try:
                stdscr.addstr(confirm_row, 2, '[ Create Game ]',
                              ptk.color_pair(ptk.COLOR_GREEN) | confirm_attr | ptk.A_BOLD)
            except Exception:
                pass
        except Exception:
            pass

        if error_msg and now < error_until:
            try:
                stdscr.addstr(rows - 2, 2, f'Error: {error_msg}'[:cols - 4],
                              ptk.color_pair(ptk.COLOR_RED) | ptk.A_BOLD)
            except Exception:
                pass

        _draw_footer(stdscr, '[↑/↓] Choose game  [←/→] Max players  [Tab/↓] Next field  [ESC] Cancel')
        stdscr.refresh()

        ch = stdscr.getch()
        if ch == -1:
            continue
        if ch == 27:
            return {'action': 'cancel'}

        if field == 0:
            if ch in (ptk.KEY_UP, ord('w')):
                sel_game = (sel_game - 1) % len(GAME_TYPES)
            elif ch in (ptk.KEY_DOWN, ord('s')):
                sel_game = (sel_game + 1) % len(GAME_TYPES)
            elif is_enter_key(ch) or ch in (ptk.KEY_RIGHT, 9):  # 9=Tab
                field = 1
        elif field == 1:
            if ch in (ptk.KEY_LEFT, ord('a')):
                sel_max = max(0, sel_max - 1)
            elif ch in (ptk.KEY_RIGHT, ord('d')):
                sel_max = min(len(max_opts) - 1, sel_max + 1)
            elif is_enter_key(ch) or ch in (ptk.KEY_DOWN, 9):
                field = 2
            elif ch == ptk.KEY_UP:
                field = 0
        elif field == 2:
            if is_enter_key(ch) or ch in (ptk.KEY_DOWN, 9):
                # Validate password before advancing
                if password and (len(password) < 4 or not password.isalnum()):
                    pw_error_msg = 'Password must be 4-12 alphanumeric characters.'
                    pw_error_until = now + 4.0
                else:
                    pw_error_msg = ''
                    field = 3
            elif ch in (ptk.KEY_BACKSPACE, 127, 8):
                password = password[:-1]
                pw_error_msg = ''
            elif ch == ptk.KEY_UP:
                field = 1
            elif 32 <= ch <= 126:
                c = chr(ch)
                if len(password) >= 12:
                    pw_error_msg = 'Max 12 characters.'
                    pw_error_until = now + 2.0
                elif c.isalnum():
                    password += c
                    pw_error_msg = ''
                else:
                    pw_error_msg = 'Only letters and numbers allowed.'
                    pw_error_until = now + 2.0
        elif field == 3:
            if is_enter_key(ch):
                game_type = GAME_TYPES[sel_game]
                max_players = max_opts[sel_max]
                payload = {
                    'gameType': game_type,
                    'maxPlayers': max_players,
                    'playerName': player_name,
                }
                if password:
                    payload['password'] = password
                socket_client.emit('lobby:create', payload)
            elif ch == ptk.KEY_UP:
                field = 2


# ── Screen: Join by Code ──────────────────────────────────────────────────────

def join_by_code(stdscr, socket_client, player_name):
    """
    Prompt for a lobby ID (and optional password) to join a private lobby.
    Returns: {'action': 'joined', 'lobby': data} or {'action': 'cancel'}.
    """
    lobby_code = ''
    password = ''
    field = 0
    error_msg = ''
    error_until = 0.0
    pw_error_msg = ''
    pw_error_until = 0.0

    stdscr.nodelay(True)
    stdscr.timeout(100)

    while True:
        now = time.time()
        cols, rows = _get_size(stdscr)

        for event, data in socket_client.poll():
            if event == 'lobby:joined':
                return {'action': 'joined', 'lobby': data}
            elif event == 'lobby:error':
                error_msg = data.get('message', 'Error')
                error_until = now + 4.0

        stdscr.erase()
        _draw_header(stdscr, 'JOIN BY CODE')

        try:
            stdscr.addstr(2, 2, 'Lobby Code:',
                          ptk.color_pair(ptk.COLOR_YELLOW) | ptk.A_BOLD)
            code_attr = ptk.A_REVERSE if field == 0 else ptk.A_NORMAL
            stdscr.addstr(2, 14, (lobby_code or ' _ ')[:cols - 16],
                          ptk.color_pair(ptk.COLOR_CYAN) | code_attr)

            stdscr.addstr(4, 2, 'Password (leave blank if none):',
                          ptk.color_pair(ptk.COLOR_YELLOW) | ptk.A_BOLD)
            pw_attr = ptk.A_REVERSE if field == 1 else ptk.A_NORMAL
            # Password shown in plain text
            pw_display = password + '_'
            stdscr.addstr(4, 34, pw_display[:cols - 36],
                          ptk.color_pair(ptk.COLOR_CYAN) | pw_attr)

            # Error below password field
            if pw_error_msg and now < pw_error_until:
                try:
                    stdscr.addstr(5, 4, pw_error_msg[:cols - 8],
                                  ptk.color_pair(ptk.COLOR_RED) | ptk.A_BOLD)
                except Exception:
                    pass

            join_row = 7
            join_attr = ptk.A_REVERSE if field == 2 else ptk.A_NORMAL
            stdscr.addstr(join_row, 2, '[ Join ]',
                          ptk.color_pair(ptk.COLOR_GREEN) | join_attr | ptk.A_BOLD)
        except Exception:
            pass

        if error_msg and now < error_until:
            try:
                stdscr.addstr(rows - 2, 2, f'Error: {error_msg}'[:cols - 4],
                              ptk.color_pair(ptk.COLOR_RED) | ptk.A_BOLD)
            except Exception:
                pass

        _draw_footer(stdscr, '[↑/↓] Move between fields  [Tab/Enter] Next field  [Enter on Join] Submit  [ESC] Back')
        stdscr.refresh()

        ch = stdscr.getch()
        if ch == -1:
            continue
        if ch == 27:
            return {'action': 'cancel'}

        if field == 0:
            if is_enter_key(ch) or ch == 9:  # 9=Tab
                field = 1
            elif ch in (ptk.KEY_DOWN,):
                field = 1
            elif ch in (ptk.KEY_BACKSPACE, 127, 8):
                lobby_code = lobby_code[:-1]
            elif 32 <= ch <= 126 and len(lobby_code) < 16:
                lobby_code += chr(ch)
        elif field == 1:
            if is_enter_key(ch) or ch == 9:
                field = 2
            elif ch == ptk.KEY_UP:
                field = 0
            elif ch in (ptk.KEY_DOWN,):
                field = 2
            elif ch in (ptk.KEY_BACKSPACE, 127, 8):
                password = password[:-1]
                pw_error_msg = ''
            elif 32 <= ch <= 126:
                c = chr(ch)
                if c.isalnum() and len(password) < 12:
                    password += c
                    pw_error_msg = ''
                elif not c.isalnum():
                    pw_error_msg = 'Only letters and numbers allowed.'
                    pw_error_until = now + 2.0
        elif field == 2:
            if is_enter_key(ch) and lobby_code:
                payload = {'lobbyId': lobby_code, 'playerName': player_name}
                if password:
                    payload['password'] = password
            elif ch == ptk.KEY_UP:
                field = 1
                socket_client.emit('lobby:join', payload)


# ── Screen: Waiting Room ──────────────────────────────────────────────────────

def waiting_room(stdscr, socket_client, player_name, lobby_info, my_slot, password=''):
    """
    Display connected players and wait for host to start.
    Returns:
        {'action': 'start', 'data': game_start_data}    — game:start received
        {'action': 'quit'}                               — ESC / dissolved
    """
    players = lobby_info.get('players', [])
    lobby_id = lobby_info.get('lobbyId', '????')
    game_type = lobby_info.get('gameType', '?')
    max_players = lobby_info.get('maxPlayers', 2)
    is_host = (my_slot == 0)
    # Use server-provided createdAt (ms epoch) if available, else now
    created_at_ms = lobby_info.get('createdAt', int(time.time() * 1000))
    expires_at = created_at_ms / 1000.0 + LOBBY_TIMEOUT_SECONDS

    stdscr.nodelay(True)
    stdscr.timeout(100)

    while True:
        cols, rows = _get_size(stdscr)

        for event, data in socket_client.poll():
            if event == 'lobby:player_joined':
                players = data.get('players', players)
            elif event == 'lobby:player_left':
                players = data.get('players', players)
                new_host = data.get('newHostSocketId')
                if new_host is not None:
                    # We might have become host
                    my_player = next((p for p in players if p.get('slot') == my_slot), None)
                    if my_player:
                        is_host = True
            elif event == 'lobby:dissolved':
                return {'action': 'quit', 'reason': 'Lobby was dissolved.'}
            elif event == 'game:request_size':
                # Server is negotiating arena size before game:start — reply immediately
                r_cols, r_rows = _get_size(stdscr)
                socket_client.emit('game:report_size', {'cols': r_cols, 'rows': r_rows})
            elif event == 'game:start':
                return {'action': 'start', 'data': data}
            elif event == '_disconnected':
                return {'action': 'quit', 'reason': 'Disconnected from server.'}

        stdscr.erase()
        _draw_header(stdscr, 'WAITING ROOM')

        now = time.time()
        remaining = max(0, int(expires_at - now))
        timer_color = ptk.COLOR_RED if remaining < 60 else ptk.COLOR_WHITE

        try:
            game_label = GAME_TYPE_LABELS.get(game_type, game_type)
            stdscr.addstr(2, 2, f'Game: {game_label}',
                          ptk.color_pair(ptk.COLOR_CYAN) | ptk.A_BOLD)
            stdscr.addstr(3, 2, f'Lobby Code: {lobby_id}',
                          ptk.color_pair(ptk.COLOR_WHITE))
            pw_display = password if password else 'Public'
            stdscr.addstr(4, 2, f'Password: {pw_display}',
                          ptk.color_pair(ptk.COLOR_WHITE))
            stdscr.addstr(5, 2, f'Players: {len(players)}/{max_players}',
                          ptk.color_pair(ptk.COLOR_WHITE))
            mins, secs = divmod(remaining, 60)
            stdscr.addstr(5, 24, f'Expires in: {mins}:{secs:02d}',
                          ptk.color_pair(timer_color))
        except Exception:
            pass

        # Auto-expire check
        if remaining == 0:
            socket_client.emit('lobby:leave')
            return {'action': 'quit', 'reason': 'Lobby expired.'}

        slot_colors = [
            ptk.COLOR_GREEN,
            ptk.COLOR_BLUE,
            ptk.COLOR_YELLOW,
            ptk.COLOR_MAGENTA,
        ]
        try:
            stdscr.addstr(7, 2, 'Slots:', ptk.color_pair(ptk.COLOR_YELLOW) | ptk.A_BOLD)
        except Exception:
            pass
        for i in range(max_players):
            player = next((p for p in players if p.get('slot') == i), None)
            color = slot_colors[i % len(slot_colors)]
            indicator = '►' if i == my_slot else ' '
            if player:
                tag = '(you)' if i == my_slot else ('(host)' if i == 0 else '')
                line = f'{indicator} Slot {i + 1}: {player.get("name", "Player")} {tag}'
            else:
                if max_players == 1:
                    line = f'  Slot {i + 1}: [ AI ]'
                else:
                    line = f'  Slot {i + 1}: [ waiting... ]'
            try:
                stdscr.addstr(8 + i, 4, line[:cols - 6],
                              ptk.color_pair(color) | (ptk.A_BOLD if i == my_slot else ptk.A_NORMAL))
            except Exception:
                pass

        # Status message
        msg_row = 8 + max_players + 1
        if is_host:
            try:
                start_ready = len(players) >= 1 if max_players == 1 else len(players) >= 2
                attr = ptk.color_pair(ptk.COLOR_GREEN) | ptk.A_BOLD
                if start_ready:
                    if max_players == 1:
                        stdscr.addstr(msg_row, 2, 'Press ENTER to Play!', attr)
                    else:
                        stdscr.addstr(msg_row, 2, 'Press ENTER to Start the game!', attr)
                else:
                    stdscr.addstr(msg_row, 2, 'Waiting for more players...    ', attr)
            except Exception:
                pass
        else:
            try:
                stdscr.addstr(msg_row, 2, 'Waiting for host to start...',
                              ptk.color_pair(ptk.COLOR_WHITE))
            except Exception:
                pass

        _draw_footer(stdscr, '[ESC] Leave Lobby' + ('  [Enter] Start' if is_host else ''))
        stdscr.refresh()

        ch = stdscr.getch()
        if ch == -1:
            continue
        if ch == 27:
            socket_client.emit('lobby:leave')
            return {'action': 'quit'}
        start_threshold = 1 if max_players == 1 else 2
        if is_enter_key(ch) and is_host and len(players) >= start_threshold:
            min_c, min_r = GAME_MIN_SIZES.get(game_type, (0, 0))
            cur_c, cur_r = _get_size(stdscr)
            if cur_c < min_c or cur_r < min_r:
                # Show error briefly on the existing status row
                try:
                    stdscr.addstr(msg_row + 1, 2,
                                  f'Terminal too small! Need {min_c}x{min_r} (have {cur_c}x{cur_r}).',
                                  ptk.color_pair(ptk.COLOR_RED) | ptk.A_BOLD)
                    stdscr.refresh()
                    import time as _time; _time.sleep(2.0)
                except Exception:
                    pass
            else:
                socket_client.emit('lobby:start')


# ── High-level Lobby Flow ─────────────────────────────────────────────────────

def run_lobby_flow(stdscr, socket_client, player_name):
    """
    Orchestrate the full lobby browser → create/join → waiting room flow.

    Returns:
        {'action': 'start', 'data': game_start_data}  — proceed to game
        {'action': 'quit'}                             — user quit
    """
    while True:
        result = lobby_browser(stdscr, socket_client, player_name)
        action = result.get('action')

        if action == 'quit':
            return {'action': 'quit'}

        elif action == 'create':
            cr = create_lobby(stdscr, socket_client, player_name)
            if cr.get('action') == 'created':
                lobby_data = cr['lobby']
                pw = cr.get('password', '')
                my_slot = 0
                wr = waiting_room(stdscr, socket_client, player_name,
                                  lobby_data, my_slot, password=pw)
                if wr.get('action') == 'start':
                    return wr
                # else fell back to browser

        elif action == 'join_code':
            jr = join_by_code(stdscr, socket_client, player_name)
            if jr.get('action') == 'joined':
                lobby_data = jr['lobby']
                my_slot = lobby_data.get('mySlot', 1)
                wr = waiting_room(stdscr, socket_client, player_name,
                                  lobby_data, my_slot)
                if wr.get('action') == 'start':
                    return wr

        elif action == 'join':
            lobby = result.get('lobby', {})
            lobby_id = lobby.get('lobbyId', '')
            if not lobby_id:
                continue

            if lobby.get('hasPassword'):
                # Use retry-capable password screen
                joined_data = _join_with_password_retry(stdscr, socket_client, player_name, lobby_id)
                if joined_data is None:
                    continue  # cancelled
            else:
                payload = {'lobbyId': lobby_id, 'playerName': player_name}
                socket_client.emit('lobby:join', payload)
                joined_data = _wait_for_join(stdscr, socket_client)
                if joined_data is None:
                    continue

            my_slot = joined_data.get('mySlot', 1)
            wr = waiting_room(stdscr, socket_client, player_name,
                              joined_data, my_slot)
            if wr.get('action') == 'start':
                return wr


def _join_with_password_retry(stdscr, socket_client, player_name, lobby_id):
    """
    Password entry screen for joining a private lobby from the browser.
    Allows unlimited retries — error shows below the field and fades.
    Returns joined lobby data dict, or None if cancelled.
    """
    password = ''
    error_msg = ''
    error_until = 0.0

    stdscr.nodelay(True)
    stdscr.timeout(100)

    while True:
        now = time.time()
        cols, rows = _get_size(stdscr)

        for event, data in socket_client.poll():
            if event == 'lobby:joined':
                return data
            elif event == 'lobby:error':
                error_msg = data.get('message', 'Incorrect password. Try again.')
                error_until = now + 3.0
                password = ''   # clear for retry

        stdscr.erase()
        _draw_header(stdscr, 'ENTER PASSWORD')

        try:
            stdscr.addstr(2, 2, f'This lobby is password protected.',
                          ptk.color_pair(ptk.COLOR_WHITE))
            stdscr.addstr(3, 2, f'Lobby: {lobby_id}',
                          ptk.color_pair(ptk.COLOR_WHITE) | ptk.A_DIM)
            stdscr.addstr(5, 2, 'Password:',
                          ptk.color_pair(ptk.COLOR_YELLOW) | ptk.A_BOLD)
            stdscr.addstr(5, 12, (password or '') + '_',
                          ptk.color_pair(ptk.COLOR_CYAN) | ptk.A_REVERSE)
            if error_msg and now < error_until:
                stdscr.addstr(6, 4, error_msg[:cols - 8],
                              ptk.color_pair(ptk.COLOR_RED) | ptk.A_BOLD)
        except Exception:
            pass

        _draw_footer(stdscr, '[Enter] Submit  [ESC] Cancel')
        stdscr.refresh()

        ch = stdscr.getch()
        if ch == -1:
            continue
        if ch == 27:
            return None
        elif is_enter_key(ch):
            payload = {'lobbyId': lobby_id, 'playerName': player_name, 'password': password}
            socket_client.emit('lobby:join', payload)
        elif ch in (ptk.KEY_BACKSPACE, 127, 8):
            password = password[:-1]
        elif 32 <= ch <= 126 and len(password) < 32:
            password += chr(ch)


def _wait_for_join(stdscr, socket_client, timeout=8.0):
    """Block until lobby:joined arrives (for non-password joins). Returns data or None."""
    deadline = time.time() + timeout
    stdscr.nodelay(True)
    stdscr.timeout(200)
    cols, rows = _get_size(stdscr)

    while time.time() < deadline:
        elapsed = timeout - (deadline - time.time())
        try:
            spinner = '|/-\\'[int(elapsed * 4) % 4]
            stdscr.addstr(rows // 2, 2,
                          f'{spinner} Joining lobby...',
                          ptk.color_pair(ptk.COLOR_CYAN))
            stdscr.refresh()
        except Exception:
            pass

        for event, data in socket_client.poll():
            if event == 'lobby:joined':
                return data
            if event == 'lobby:error':
                try:
                    stdscr.addstr(rows // 2, 2,
                                  f'Error: {data.get("message", "?")}',
                                  ptk.color_pair(ptk.COLOR_RED) | ptk.A_BOLD)
                    stdscr.refresh()
                except Exception:
                    pass
                time.sleep(2)
                return None

        stdscr.getch()  # consume -1

    return None
