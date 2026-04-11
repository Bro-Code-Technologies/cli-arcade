import { Server, Socket } from 'socket.io';
import crypto from 'crypto';
import bcrypt from 'bcrypt';
import {
  ILobby,
  ILobbyInfo,
  ILobbyPlayer,
  ILobbyCreatePayload,
  ILobbyJoinPayload,
  IGameStartPayload,
  IGameReportSizePayload,
} from '../cli-arcade-mp.interfaces';

// Re-export types with local aliases
type GameType = 'star_ship_2' | 'kernel_kings';
type LobbyStatus = 'waiting' | 'starting' | 'in_game' | 'finished';

// ── In-memory store ───────────────────────────────────────────────────────────

const lobbies = new Map<string, ILobby>();
/** Rate limiting: socket ID → timestamps of lobby:create calls */
const createRateMap = new Map<string, number[]>();

// ── Helpers ───────────────────────────────────────────────────────────────────

const sanitizeLobby = (lobby: ILobby): ILobbyInfo => ({
  lobbyId: lobby.lobbyId,
  gameType: lobby.gameType,
  maxPlayers: lobby.maxPlayers,
  playerCount: lobby.players.length,
  status: lobby.status,
  hostName: lobby.players.find((p) => p.socketId === lobby.hostSocketId)?.name ?? 'Unknown',
  hasPassword: lobby.passwordHash !== null,
});

const findLobbyBySocket = (socketId: string): ILobby | undefined => {
  for (const lobby of lobbies.values()) {
    if (lobby.players.some((p) => p.socketId === socketId)) return lobby;
  }
  return undefined;
};

const publicLobbies = (): ILobbyInfo[] =>
  Array.from(lobbies.values())
    .filter((l) => l.status === 'waiting')
    .map(sanitizeLobby);

const isRateLimited = (socketId: string): boolean => {
  const now = Date.now();
  const windowMs = 60_000;
  const maxPerWindow = 5;
  const timestamps = (createRateMap.get(socketId) ?? []).filter((t) => now - t < windowMs);
  if (timestamps.length >= maxPerWindow) return true;
  timestamps.push(now);
  createRateMap.set(socketId, timestamps);
  return false;
};

const LOBBY_TIMEOUT_MS = 5 * 60 * 1000; // 5 minutes

/** Remove stale waiting lobbies and notify members */
const purgeStaleLobbies = (mp: ReturnType<Server['of']>): void => {
  const now = Date.now();
  for (const [id, lobby] of lobbies.entries()) {
    if (lobby.status === 'waiting' && now - lobby.createdAt > LOBBY_TIMEOUT_MS) {
      mp.to(`lobby:${id}`).emit('lobby:dissolved', { reason: 'Lobby expired.' });
      lobbies.delete(id);
      gameEngines.delete(id);
      mp.emit('lobby:list', publicLobbies()); // push fresh list to all browsers immediately
    }
  }
};

// ── Size negotiation helpers ──────────────────────────────────────────────────

/** Per-lobby terminal sizes collected during size negotiation */
const pendingSizes = new Map<string, Map<string, { cols: number; rows: number }>>();

async function negotiateArena(
  namespace: ReturnType<Server['of']>,
  lobby: ILobby,
): Promise<{ arenaWidth: number; arenaHeight: number }> {
  const lobbyId = lobby.lobbyId;
  const sizeMap = new Map<string, { cols: number; rows: number }>();
  pendingSizes.set(lobbyId, sizeMap);

  // Ask all players for their terminal size
  namespace.to(`lobby:${lobbyId}`).emit('game:request_size');

  // Wait up to 2 seconds for responses
  await new Promise<void>((resolve) => setTimeout(resolve, 2000));

  pendingSizes.delete(lobbyId);

  // Default if no responses
  const defaultCols = 80;
  const defaultRows = 24;

  let minCols = defaultCols;
  let minRows = defaultRows;

  if (sizeMap.size > 0) {
    for (const sz of sizeMap.values()) {
      if (sz.cols < minCols) minCols = sz.cols;
      if (sz.rows < minRows) minRows = sz.rows;
    }
  }

  // Leave 2-char margin from terminal edges to prevent auto-scroll at the bottom-right corner
  const arenaWidth = Math.min(220, Math.max(60, minCols - 2));
  const arenaHeight = Math.min(60, Math.max(20, minRows - 2));

  return { arenaWidth, arenaHeight };
}

// ── Import game engines ───────────────────────────────────────────────────────

import { StarShip2Engine } from './engines/star-ship-2.engine';
import { KernelKingsEngine } from './engines/kernel-kings.engine';

/** Active game engines keyed by lobbyId */
const gameEngines = new Map<string, StarShip2Engine | KernelKingsEngine>();

// ── Namespace registration ────────────────────────────────────────────────────

export const registerCliArcadeMultiplayer = (io: Server): void => {
  const mp = io.of('/cli-arcade-mp');

  setInterval(() => purgeStaleLobbies(mp), 60_000);

  mp.on('connection', (socket: Socket) => {
    const playerName: string =
      (socket.handshake.auth?.playerName as string | undefined) ?? 'Player';

    // ── lobby:list ──────────────────────────────────────────────────────────
    socket.on('lobby:list', () => {
      socket.emit('lobby:list', publicLobbies());
    });

    // ── lobby:create ────────────────────────────────────────────────────────
    socket.on('lobby:create', async (payload: ILobbyCreatePayload) => {
      if (isRateLimited(socket.id)) {
        socket.emit('lobby:error', { message: 'Too many lobbies created. Please wait.', code: 'RATE_LIMITED' });
        return;
      }

      const gameType: GameType = payload.gameType ?? 'star_ship_2';
      const maxPlayers = Math.min(4, Math.max(1, payload.maxPlayers ?? 2));
      const name = (payload.playerName ?? playerName).slice(0, 20) || 'Player';

      let passwordHash: string | null = null;
      if (payload.password) {
        passwordHash = await bcrypt.hash(payload.password, 10);
      }

      const lobbyId = crypto.randomBytes(4).toString('hex');
      const hostPlayer: ILobbyPlayer = { socketId: socket.id, name, slot: 0 };

      const lobby: ILobby = {
        lobbyId,
        gameType,
        maxPlayers,
        status: 'waiting',
        hostSocketId: socket.id,
        passwordHash,
        players: [hostPlayer],
        createdAt: Date.now(),
        lastActiveAt: Date.now(),
      };

      lobbies.set(lobbyId, lobby);
      socket.join(`lobby:${lobbyId}`);

      socket.emit('lobby:created', {
        lobbyId,
        players: lobby.players,
        gameType,
        maxPlayers,
        mySlot: 0,
        createdAt: lobby.createdAt,
      });
    });

    // ── lobby:join ──────────────────────────────────────────────────────────
    socket.on('lobby:join', async (payload: ILobbyJoinPayload) => {
      const lobby = lobbies.get(payload.lobbyId);
      if (!lobby) {
        socket.emit('lobby:error', { message: 'Lobby not found.', code: 'NOT_FOUND' });
        return;
      }
      if (lobby.status !== 'waiting') {
        socket.emit('lobby:error', { message: 'Game already in progress.', code: 'IN_PROGRESS' });
        return;
      }
      if (lobby.players.length >= lobby.maxPlayers) {
        socket.emit('lobby:error', { message: 'Lobby is full.', code: 'FULL' });
        return;
      }
      if (lobby.passwordHash) {
        const provided = payload.password ?? '';
        const match = await bcrypt.compare(provided, lobby.passwordHash);
        if (!match) {
          socket.emit('lobby:error', { message: 'Incorrect password.', code: 'WRONG_PASSWORD' });
          return;
        }
      }

      const name = (payload.playerName ?? playerName).slice(0, 20) || 'Player';
      const slot = lobby.players.length;
      const newPlayer: ILobbyPlayer = { socketId: socket.id, name, slot };
      lobby.players.push(newPlayer);
      lobby.lastActiveAt = Date.now();
      socket.join(`lobby:${lobby.lobbyId}`);

      socket.emit('lobby:joined', {
        lobbyId: lobby.lobbyId,
        players: lobby.players,
        mySlot: slot,
        gameType: lobby.gameType,
        maxPlayers: lobby.maxPlayers,
        createdAt: lobby.createdAt,
      });

      socket.to(`lobby:${lobby.lobbyId}`).emit('lobby:player_joined', {
        player: newPlayer,
        players: lobby.players,
      });
    });

    // ── lobby:leave ─────────────────────────────────────────────────────────
    socket.on('lobby:leave', () => {
      handleLeave(socket, mp);
    });

    // ── lobby:start ─────────────────────────────────────────────────────────
    socket.on('lobby:start', async () => {
      const lobby = findLobbyBySocket(socket.id);
      if (!lobby) return;
      if (lobby.hostSocketId !== socket.id) {
        socket.emit('lobby:error', { message: 'Only the host can start the game.', code: 'NOT_HOST' });
        return;
      }
      const minPlayers = lobby.maxPlayers === 1 ? 1 : 2;
      if (lobby.players.length < minPlayers) {
        socket.emit('lobby:error', { message: 'Need at least 2 players to start.', code: 'NOT_ENOUGH_PLAYERS' });
        return;
      }

      lobby.status = 'starting';

      // Negotiate arena size
      const { arenaWidth, arenaHeight } = await negotiateArena(mp, lobby);

      lobby.status = 'in_game';

      const seed = Math.floor(Math.random() * 2 ** 31);

      const startPayload: IGameStartPayload = {
        gameType: lobby.gameType,
        mySlot: -1, // overridden per-player below
        players: lobby.players,
        arenaWidth,
        arenaHeight,
        seed,
      };

      // Emit game:start to each player with their individual slot
      for (const player of lobby.players) {
        const playerSocket = mp.sockets.get(player.socketId);
        if (playerSocket) {
          playerSocket.emit('game:start', { ...startPayload, mySlot: player.slot });
        }
      }

      // Delay engine start slightly so clients have time to transition from
      // the waiting room to the game screen before the first game:state arrives.
      // Without this delay, game:state is emitted in the same event-loop tick as
      // game:start and gets silently dropped by the client lobby poller.
      await new Promise<void>((resolve) => setTimeout(resolve, 400));

      // Start the appropriate engine
      if (lobby.gameType === 'star_ship_2') {
        const engine = new StarShip2Engine(lobby, mp, arenaWidth, arenaHeight);
        gameEngines.set(lobby.lobbyId, engine);
        engine.start();
      } else if (lobby.gameType === 'kernel_kings') {
        const engine = new KernelKingsEngine(lobby, mp);
        gameEngines.set(lobby.lobbyId, engine);
        engine.start();
      }
    });

    // ── game:report_size ────────────────────────────────────────────────────
    socket.on('game:report_size', (payload: IGameReportSizePayload) => {
      const lobby = findLobbyBySocket(socket.id);
      if (!lobby) return;
      const sizeMap = pendingSizes.get(lobby.lobbyId);
      if (sizeMap) {
        sizeMap.set(socket.id, { cols: payload.cols ?? 80, rows: payload.rows ?? 24 });
      }
    });

    // ── game:input (Star Ship 2) ─────────────────────────────────────────────
    socket.on('game:input', (payload: { direction: [number, number]; tick: number }) => {
      const lobby = findLobbyBySocket(socket.id);
      if (!lobby) return;
      const engine = gameEngines.get(lobby.lobbyId);
      if (engine instanceof StarShip2Engine) {
        engine.handleInput(socket.id, payload.direction);
      }
    });

    // ── game:move (Kernel Kings) ─────────────────────────────────────────────
    socket.on('game:move', (payload: { from: { row: number; col: number }; to: { row: number; col: number } }) => {
      const lobby = findLobbyBySocket(socket.id);
      if (!lobby) return;
      const engine = gameEngines.get(lobby.lobbyId);
      if (engine instanceof KernelKingsEngine) {
        engine.handleMove(socket.id, payload.from, payload.to);
      }
    });

    // ── disconnect ───────────────────────────────────────────────────────────
    socket.on('disconnect', () => {
      handleLeave(socket, mp);
      createRateMap.delete(socket.id);
    });
  });
};

// ── Shared leave/disconnect logic ─────────────────────────────────────────────

function handleLeave(socket: Socket, mp: ReturnType<Server['of']>): void {
  const lobby = findLobbyBySocket(socket.id);
  if (!lobby) return;

  const wasHost = lobby.hostSocketId === socket.id;
  lobby.players = lobby.players.filter((p) => p.socketId !== socket.id);
  lobby.lastActiveAt = Date.now();

  // Leave the socket room so the player never receives stale events for this lobby
  socket.leave(`lobby:${lobby.lobbyId}`);

  // Notify game engine only when a game is actually in progress (prevents stale timers
  // from firing into a subsequent game after this player presses Enter on the game-over screen)
  const engine = gameEngines.get(lobby.lobbyId);
  if (lobby.status === 'in_game') {
    if (engine instanceof KernelKingsEngine) {
      engine.handleDisconnect(socket.id);
    } else if (engine instanceof StarShip2Engine) {
      engine.handleDisconnect(socket.id);
    }
  }

  if (lobby.players.length === 0) {
    // Dissolve empty lobby
    lobbies.delete(lobby.lobbyId);
    gameEngines.delete(lobby.lobbyId);
    mp.emit('lobby:list', publicLobbies());
    return;
  }

  if (wasHost && lobby.status === 'waiting') {
    // Host left waiting room — dissolve lobby and notify remaining players
    mp.to(`lobby:${lobby.lobbyId}`).emit('lobby:dissolved', { reason: 'Host left the lobby.' });
    lobbies.delete(lobby.lobbyId);
    mp.emit('lobby:list', publicLobbies());
  } else if (wasHost && lobby.status === 'in_game') {
    // Host left during a game — dissolve and notify remaining players
    mp.to(`lobby:${lobby.lobbyId}`).emit('lobby:dissolved', { reason: 'Host left the game.' });
    if (engine instanceof StarShip2Engine || engine instanceof KernelKingsEngine) {
      engine.stop();
    }
    gameEngines.delete(lobby.lobbyId);
    lobbies.delete(lobby.lobbyId);
    mp.emit('lobby:list', publicLobbies());
  } else {
    mp.to(`lobby:${lobby.lobbyId}`).emit('lobby:player_left', {
      socketId: socket.id,
      players: lobby.players,
    });
  }
}
