import json
import os
import shutil
import warnings

try:
    import appdirs
except Exception:
    appdirs = None


class HighScores:
    """Per-game highscores stored in a user-writable location.

    Constructor is backward-compatible: `HighScores(game, default)` works.
    If legacy highscores exist under the project `games/<game>/highscores.json`,
    they will be migrated to the user data directory on first use.
    """

    def __init__(self, game, default=None, appname='cli-arcade', appauthor=None):
        if default is None:
            default = {'score': {'player': 'Player', 'value': 0}}
        # copy default to avoid shared mutable state
        try:
            self.default = {k: v.copy() for k, v in default.items()}
        except Exception:
            self.default = dict(default)

        self.game = game
        self.appname = appname
        self.appauthor = appauthor

        # determine user-writable base
        base = None
        if appdirs is not None:
            try:
                base = appdirs.user_data_dir(self.appname, self.appauthor)
            except Exception:
                base = None

        if not base:
            home = os.path.expanduser('~') or os.getcwd()
            base = os.path.join(home, f'.{self.appname}')

        self.dir = os.path.abspath(os.path.join(base, 'games', game))
        self.path = os.path.join(self.dir, 'highscores.json')

        # attempt migration from project-root location if present
        try:
            proj_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
            legacy = os.path.join(proj_root, 'games', game, 'highscores.json')
            if os.path.exists(legacy) and not os.path.exists(self.path):
                try:
                    os.makedirs(os.path.dirname(self.path), exist_ok=True)
                    shutil.copy2(legacy, self.path)
                except Exception as e:
                    warnings.warn(f"Failed to migrate legacy highscores for {game}: {e}")
        except Exception:
            pass

    def _path(self):
        return self.path

    def load(self):
        path = self._path()
        try:
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        for k, v in self.default.items():
                            if k not in data or not isinstance(data[k], dict):
                                data[k] = v.copy()
                            else:
                                data[k]['player'] = data[k].get('player', v.get('player'))
                                data[k]['value'] = data[k].get('value', v.get('value'))
                        return data
        except Exception as e:
            warnings.warn(f"HighScores.load() failed for {path}: {e}")

        try:
            return {k: v.copy() for k, v in self.default.items()}
        except Exception:
            return dict(self.default)

    def save(self, data):
        path = self._path()
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
        except Exception as e:
            warnings.warn(f"HighScores.save() failed to create dir: {e}")
            return False

        try:
            tmp = path + '.tmp'
            with open(tmp, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp, path)
            return True
        except Exception as e:
            warnings.warn(f"HighScores.save() write failed for {path}: {e}")
            try:
                with open(path, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                return True
            except Exception as e2:
                warnings.warn(f"HighScores.save() fallback write failed for {path}: {e2}")
                return False
