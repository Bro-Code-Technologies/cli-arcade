// ─── Shared Types: CLI Arcade Multiplayer (/cli-arcade-mp namespace) ──────────

// ── Core structures ────────────────────────────────────────────────────────────

export interface ICoord {
  row: number;
  col: number;
}

export type GameType = 'star_ship_2' | 'kernel_kings';

export type LobbyStatus = 'waiting' | 'starting' | 'in_game' | 'finished';

export interface ILobbyPlayer {
  socketId: string;
  name: string;
  slot: number;
}

/** Full lobby (server-internal — includes passwordHash) */
export interface ILobby {
  lobbyId: string;
  gameType: GameType;
  maxPlayers: number;
  status: LobbyStatus;
  hostSocketId: string;
  passwordHash: string | null;
  players: ILobbyPlayer[];
  createdAt: number;
  lastActiveAt: number;
}

/** Sanitised lobby safe to send to clients */
export interface ILobbyInfo {
  lobbyId: string;
  gameType: GameType;
  maxPlayers: number;
  playerCount: number;
  status: LobbyStatus;
  hostName: string;
  hasPassword: boolean;
}

// ── Lobby event payloads ─────────────────────────────────────────────────────

export interface ILobbyCreatePayload {
  gameType: GameType;
  maxPlayers: number;
  password?: string;
  playerName?: string;
}

export interface ILobbyJoinPayload {
  lobbyId: string;
  password?: string;
  playerName?: string;
}

export interface ILobbyCreatedPayload {
  lobbyId: string;
  players: ILobbyPlayer[];
  gameType: GameType;
  maxPlayers: number;
  createdAt: number;
}

export interface ILobbyJoinedPayload {
  lobbyId: string;
  players: ILobbyPlayer[];
  mySlot: number;
  gameType: GameType;
  maxPlayers: number;
  createdAt: number;
}

export interface ILobbyPlayerJoinedPayload {
  player: ILobbyPlayer;
  players: ILobbyPlayer[];
}

export interface ILobbyPlayerLeftPayload {
  socketId: string;
  players: ILobbyPlayer[];
  newHostSocketId?: string;
}

export interface ILobbyErrorPayload {
  message: string;
  code: string;
}

// ── Size negotiation ─────────────────────────────────────────────────────────

export interface IGameReportSizePayload {
  cols: number;
  rows: number;
}

// ── Game start ───────────────────────────────────────────────────────────────

export interface IGameStartPayload {
  gameType: GameType;
  mySlot: number;
  players: ILobbyPlayer[];
  arenaWidth: number;
  arenaHeight: number;
  seed: number;
}

// ── Star Ship 2 ──────────────────────────────────────────────────────────────

export interface ISSCoord {
  row: number;
  col: number;
}

export interface ISSPlayer {
  slot: number;
  name: string;
  alive: boolean;
  score: number;
  ship: ISSCoord[];   // [0] = head
  direction: [number, number];
}

export interface ISSStar {
  row: number;
  col: number;
  special: boolean;
}

export interface IStarShip2State {
  tick: number;
  players: ISSPlayer[];
  stars: ISSStar[];
  specialStar: ISSStar | null;
  arenaWidth: number;
  arenaHeight: number;
}

export interface ISSInputPayload {
  direction: [number, number];  // [dy, dx]
  tick: number;
}

export interface ISSPlayerDiedPayload {
  slot: number;
  cause: 'wall' | 'self' | 'collision';
}

export interface ISSGameOverPayload {
  rankings: Array<{ slot: number; name: string; score: number; alive: boolean }>;
}

// ── Kernel Kings ─────────────────────────────────────────────────────────────

export type PieceOwner = 0 | 1;

export interface IPiece {
  owner: PieceOwner;
  king: boolean;
}

export interface IBCPlayer {
  slot: PieceOwner;
  name: string;
  captures: number;
}

export type BoardCell = IPiece | null;

export interface IKernelKingsState {
  board: BoardCell[][];        // [row][col] — 8×8
  turn: PieceOwner;
  players: IBCPlayer[];
  mustJump: ICoord | null;     // if set, this piece must continue jumping
  movesSinceCapture: number;
  capturedRed: number;
  capturedBlue: number;
  turnDeadline: number;        // Unix ms when current player's time runs out
}

export interface IGameMovePayload {
  from: ICoord;
  to: ICoord;
}

export interface IInvalidMovePayload {
  reason: string;
}

export interface IBCGameOverPayload {
  winner: PieceOwner | null;  // null = draw
  reason: 'capture_all' | 'no_moves' | 'draw' | 'timeout' | 'disconnect';
  players: IBCPlayer[];
}

// ── Universal game-over result (used by MultiplayerGameBase) ─────────────────

export interface IGameOverPayload {
  gameType: GameType;
  starShip2?: ISSGameOverPayload;
  kernelKings?: IBCGameOverPayload;
}
