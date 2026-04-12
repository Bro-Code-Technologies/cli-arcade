import { RequestHandler, Router } from 'express';
import fs from 'fs';
import path from 'path';

// Path to local JSON score file — lives in server/data/ which is gitignored
const DATA_DIR = path.resolve(__dirname, '..', 'data');
const SCORES_FILE = path.join(DATA_DIR, 'scores.json');

// Score shapes (mirrors production API)
interface IMetric {
  player: string;
  value: number;
}

type GameScores = Record<string, IMetric>;
type AllScores = Record<string, GameScores>;

// Read all scores from disk. Creates the file with {} if it does not exist.
function readScores(): AllScores {
  console.log('[scores] readScores: reading from', SCORES_FILE);
  if (!fs.existsSync(SCORES_FILE)) {
    console.log('[scores] readScores: file not found, initializing empty scores file');
    writeScores({});
    return {};
  }
  try {
    const raw = fs.readFileSync(SCORES_FILE, 'utf-8');
    const parsed = JSON.parse(raw) as AllScores;
    console.log('[scores] readScores: loaded games:', Object.keys(parsed));
    return parsed;
  } catch (err) {
    console.log('[scores] readScores: parse error, returning empty -', err);
    return {};
  }
}

// Write scores to disk. Creates data/ directory if needed.
function writeScores(scores: AllScores): void {
  console.log('[scores] writeScores: writing games:', Object.keys(scores), 'to', SCORES_FILE);
  if (!fs.existsSync(DATA_DIR)) {
    console.log('[scores] writeScores: creating data directory', DATA_DIR);
    fs.mkdirSync(DATA_DIR, { recursive: true });
  }
  try {
    fs.writeFileSync(SCORES_FILE, JSON.stringify(scores, null, 2), 'utf-8');
    console.log('[scores] writeScores: write successful');
  } catch (err) {
    console.error('[scores] writeScores: write failed -', err);
    throw err;
  }
}

// Merge incoming game scores into stored scores. Keeps higher value per metric.
function mergeGameScores(stored: GameScores, incoming: GameScores): GameScores {
  const result: GameScores = { ...stored };
  for (const [metric, entry] of Object.entries(incoming)) {
    const existing = result[metric];
    if (!existing || entry.value > existing.value) {
      result[metric] = { player: entry.player, value: entry.value };
    }
  }
  return result;
}

// Validate a game scores body: must be { metric: { player: string, value: number } }
function validateGameScores(body: unknown): { scores: GameScores } | { error: string } {
  if (!body || typeof body !== 'object' || Array.isArray(body)) {
    return { error: 'Request body must be a JSON object' };
  }
  const scores: GameScores = {};
  for (const [metric, entry] of Object.entries(body as Record<string, unknown>)) {
    if (!entry || typeof entry !== 'object' || Array.isArray(entry)) {
      return { error: `Metric "${metric}" must be an object with player and value` };
    }
    const { player, value } = entry as Record<string, unknown>;
    if (typeof player !== 'string' || player.trim() === '') {
      return { error: `Metric "${metric}": player must be a non-empty string` };
    }
    const numValue = Number(value);
    if (value === undefined || value === null || isNaN(numValue)) {
      return { error: `Metric "${metric}": value must be a number` };
    }
    scores[metric] = { player: player.trim(), value: numValue };
  }
  return { scores };
}

// GET /api/apps/cli-arcade/scores — all games
const getAllScores: RequestHandler = (_req, res) => {
  console.log('[scores] GET /scores - getAllScores called');
  const scores = readScores();
  console.log('[scores] GET /scores - returning', Object.keys(scores).length, 'game(s)');
  res.status(200).json(scores);
};

// GET /api/apps/cli-arcade/scores/:game — single game
const getGameScores: RequestHandler = (req, res) => {
  const game = String(req.params.game);
  console.log(`[scores] GET /scores/${game} - getGameScores called`);
  const scores = readScores();
  const gameScores = scores[game];
  if (!gameScores) {
    console.log(`[scores] GET /scores/${game} - not found`);
    res.status(404).json('No scores found for this game');
    return;
  }
  console.log(`[scores] GET /scores/${game} - returning`, Object.keys(gameScores).length, 'metric(s)');
  res.status(200).json(gameScores);
};

// POST /api/apps/cli-arcade/scores/sync — bulk merge multiple games
const syncScores: RequestHandler = (req, res) => {
  console.log('[scores] POST /scores/sync - syncScores called, body keys:', req.body ? Object.keys(req.body) : req.body);
  const body = req.body;
  if (!body || typeof body !== 'object' || Array.isArray(body)) {
    console.log('[scores] POST /scores/sync - invalid body type:', typeof body);
    res.status(400).json('Request body must be a JSON object mapping game names to scores');
    return;
  }

  const stored = readScores();
  const result: AllScores = {};

  for (const [game, gameBody] of Object.entries(body as Record<string, unknown>)) {
    console.log(`[scores] POST /scores/sync - validating game "${game}"`);
    const validated = validateGameScores(gameBody);
    if ('error' in validated) {
      console.log(`[scores] POST /scores/sync - validation failed for "${game}":`, validated.error);
      res.status(400).json(`Game "${game}": ${validated.error}`);
      return;
    }
    stored[game] = mergeGameScores(stored[game] ?? {}, validated.scores);
    result[game] = stored[game];
    console.log(`[scores] POST /scores/sync - merged game "${game}", metrics:`, Object.keys(validated.scores));
  }

  writeScores(stored);
  console.log('[scores] POST /scores/sync - sync complete, games saved:', Object.keys(result));
  res.status(200).json(result);
};

// POST /api/apps/cli-arcade/scores/:game — save/merge scores for a game
const saveGameScores: RequestHandler = (req, res) => {
  const game = String(req.params.game);
  console.log(`[scores] POST /scores/${game} - saveGameScores called, body:`, JSON.stringify(req.body));
  const validated = validateGameScores(req.body);
  if ('error' in validated) {
    console.log(`[scores] POST /scores/${game} - validation failed:`, validated.error);
    res.status(400).json(validated.error);
    return;
  }
  console.log(`[scores] POST /scores/${game} - validated metrics:`, Object.keys(validated.scores));

  const stored = readScores();
  stored[game] = mergeGameScores(stored[game] ?? {}, validated.scores);
  writeScores(stored);
  console.log(`[scores] POST /scores/${game} - save complete`);
  res.status(200).json(stored[game]);
};

const router = Router();

// NOTE: /scores/sync must be registered before /scores/:game so Express does not
// treat "sync" as a game slug.
router.get('/scores', getAllScores);
router.post('/scores/sync', syncScores);
router.get('/scores/:game', getGameScores);
router.post('/scores/:game', saveGameScores);

export default router;
