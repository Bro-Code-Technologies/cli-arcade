from game_classes import ptk
from game_classes.tools import is_enter_key

class Menu:
    def __init__(self, game):
        self.game = game

    def prompt_name(self, prompt_y, prompt_x, max_len=12):
        name = ''
        while True:
            try:
                self.game.stdscr.addstr(prompt_y, prompt_x, ' ' * (max_len + 20))
                self.game.stdscr.addstr(prompt_y, prompt_x, f'Enter name (max {max_len}): {name}')
                self.game.stdscr.refresh()
            except Exception:
                pass
            ch = self.game.stdscr.getch()
            if is_enter_key(ch):  # Enter
                return name.strip() or 'Player'
            elif ch in (27,):
                return False
            elif ch in (ptk.KEY_BACKSPACE, 127, 8):
                name = name[:-1]
            elif 32 <= ch <= 126 and len(name) < max_len:
                name += chr(ch)
            else:
                # ignore other keys
                pass

    def display(self):
        self.game.stdscr.clear()
        h, w = self.game.stdscr.getmaxyx()
        # draw title art left-aligned where it appears in-game (above the board)
        title_height = len(self.game.title)
        for i, line in enumerate(self.game.title):
            try:
                self.game.stdscr.addstr(i, 0, line, ptk.color_pair(self.game.color) | ptk.A_BOLD)
            except Exception:
                pass

        # instructions centered under the title block
        instr_y = title_height + 1
        try:
            title_width = max((len(l) for l in self.game.title), default=0)
            instrs = ['Press ENTER to Start Game', 'Press ESC to Quit']
            for idx, instr in enumerate(instrs):
                x = max(0, (title_width - len(instr)) // 2)
                self.game.stdscr.addstr(instr_y + idx, x, instr)
        except Exception:
            pass
        self.game.stdscr.refresh()
        while True:
            ch = self.game.stdscr.getch()
            # if ch in (ord('s'), ord('S')) or ch == ptk.KEY_DOWN:
            if is_enter_key(ch):
                # prompt for name before starting, centered over the title block
                prompt_y = title_height + 3
                title_width = max((len(l) for l in self.game.title), default=0)
                max_len = 50
                prompt_prefix = f'Enter name (max {max_len}): '
                prompt_len = len(prompt_prefix) + max_len
                prompt_x = max(0, (title_width - prompt_len) // 2)
                name = self.prompt_name(prompt_y, prompt_x, max_len=max_len)
                if name is False:
                    return False
                return name
            elif ch == 27:
                return False
