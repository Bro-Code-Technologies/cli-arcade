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


def get_saved_highscores(game=None, appname='cli-arcade', appauthor=None):
    """Return a list of saved highscores.

    If ``game`` is provided, it should be the game directory name and the
    function will return a single-item list (if a saved file exists). If
    ``game`` is None the function will scan the project ``games/``
    directory and return saved highscores for every game that has a
    highscores.json file in the user data directory (or migrated legacy
    file).

    Returned value is a list of dicts: ``{'game': <name>, 'scores': <data>}``.
    Only actual saved file contents are returned (defaults injected by
    ``HighScores.load()`` are not used here).
    """
    results = []
    # Determine candidate game names
    names = []
    if game:
        names = [game]
    else:
        proj_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        games_dir = os.path.join(proj_root, 'games')
        if not os.path.isdir(games_dir):
            return results
        for entry in sorted(os.listdir(games_dir)):
            dirpath = os.path.join(games_dir, entry)
            if not os.path.isdir(dirpath):
                continue
            if entry.startswith('__'):
                continue
            names.append(entry)

    for name in names:
        hs = HighScores(name, default=None, appname=appname, appauthor=appauthor)
        path = hs._path()
        if not os.path.exists(path):
            continue
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, dict):
                results.append({'game': name, 'scores': data})
        except Exception:
            # ignore unreadable files and continue
            continue

    return results


def merge_update_highscores(scores_map, appname='cli-arcade', appauthor=None):
    """Merge incoming scores into saved highscores, keeping the higher values.

    ``scores_map`` should be a mapping from game directory name -> scores dict,
    e.g. ``{'byte_bouncer': {...}, 'star_ship': {...}}``. For each game the
    function reads the actual saved `highscores.json` (if present), compares
    each key's `value` and replaces the lower value with the higher one.

    If no saved file exists for a game, the incoming scores are saved as-is.

    Returns a list of game names that were updated (files saved).
    """
    updated_games = []
    if not isinstance(scores_map, dict):
        return updated_games

    for game_name, incoming in scores_map.items():
        if not isinstance(incoming, dict):
            continue

        hs = HighScores(game_name, default=None, appname=appname, appauthor=appauthor)
        path = hs._path()

        # load actual existing data (avoid HighScores.load() defaults)
        existing = {}
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                    if isinstance(loaded, dict):
                        existing = loaded
            except Exception:
                existing = {}

        changed = False
        # iterate incoming keys and merge
        for key, inc_val in incoming.items():
            if isinstance(inc_val, dict) and 'value' in inc_val:
                inc_value = inc_val.get('value')
                # existing value
                ex_val = existing.get(key)
                if isinstance(ex_val, dict) and 'value' in ex_val:
                    ex_value = ex_val.get('value')
                    # numeric comparison when possible
                    try:
                        inc_num = float(inc_value)
                        ex_num = float(ex_value)
                    except Exception:
                        inc_num = ex_num = None

                    if inc_num is not None and ex_num is not None:
                        if inc_num > ex_num:
                            existing[key] = {'player': inc_val.get('player'), 'value': inc_val.get('value')}
                            changed = True
                    else:
                        # fallback: if different, replace
                        if ex_val != inc_val:
                            existing[key] = inc_val
                            changed = True
                else:
                    # no existing entry -> add incoming
                    existing[key] = inc_val
                    changed = True
            else:
                # non-standard structure: replace if different
                if existing.get(key) != inc_val:
                    existing[key] = inc_val
                    changed = True

        if changed:
            try:
                hs.save(existing)
                updated_games.append(game_name)
            except Exception:
                # ignore save failures for now
                pass

    return updated_games
