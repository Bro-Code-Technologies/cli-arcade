import { Server } from 'socket.io';
import {
  ILobby,
  IKernelKingsState,
  BoardCell,
  PieceOwner,
  ICoord,
} from '../../cli-arcade-mp.interfaces';

const TURN_TIMEOUT_MS = 60_000;       // 60 seconds per turn
const DISCONNECT_GRACE_MS = 15_000;   // 15 second grace period on disconnect
const DRAW_MOVE_LIMIT = 40;           // moves without capture = draw

// ── Board helpers ─────────────────────────────────────────────────────────────

type Board = BoardCell[][];

function emptyBoard(): Board {
  return Array.from({ length: 8 }, () => new Array(8).fill(null));
}

function initBoard(): Board {
  const board = emptyBoard();
  for (let row = 0; row < 8; row++) {
    for (let col = 0; col < 8; col++) {
      if ((row + col) % 2 !== 1) continue;
      if (row < 3) board[row][col] = { owner: 0, king: false };      // red
      if (row > 4) board[row][col] = { owner: 1, king: false };      // blue
    }
  }
  return board;
}

function inBounds(row: number, col: number): boolean {
  return row >= 0 && row < 8 && col >= 0 && col < 8;
}

interface IMove {
  from: ICoord;
  to: ICoord;
  jumped: ICoord | null;
}

function legalMoves(board: Board, owner: PieceOwner, forPiece?: ICoord): IMove[] {
  const directions: [number, number][] =
    owner === 0 ? [[1, -1], [1, 1]] : [[-1, -1], [-1, 1]];
  const allDirs: [number, number][] = [[1, -1], [1, 1], [-1, -1], [-1, 1]];

  const pieces: ICoord[] = forPiece ? [forPiece] : [];
  if (!forPiece) {
    for (let r = 0; r < 8; r++) {
      for (let c = 0; c < 8; c++) {
        const cell = board[r][c];
        if (cell && cell.owner === owner) pieces.push({ row: r, col: c });
      }
    }
  }

  const jumps: IMove[] = [];
  const slides: IMove[] = [];

  for (const from of pieces) {
    const piece = board[from.row][from.col];
    if (!piece || piece.owner !== owner) continue;
    const dirs = piece.king ? allDirs : directions;

    for (const [dr, dc] of dirs) {
      const nr = from.row + dr;
      const nc = from.col + dc;
      const jr = from.row + dr * 2;
      const jc = from.col + dc * 2;

      // Slide
      if (inBounds(nr, nc) && board[nr][nc] === null) {
        slides.push({ from, to: { row: nr, col: nc }, jumped: null });
      }

      // Jump
      if (inBounds(nr, nc) && inBounds(jr, jc)) {
        const over = board[nr][nc];
        if (over && over.owner !== owner && board[jr][jc] === null) {
          jumps.push({ from, to: { row: jr, col: jc }, jumped: { row: nr, col: nc } });
        }
      }
    }
  }

  // Mandatory jumps
  return jumps.length > 0 ? jumps : slides;
}

// ── Engine ────────────────────────────────────────────────────────────────────

export class KernelKingsEngine {
  private lobby: ILobby;
  private mp: ReturnType<Server['of']>;
  private state: IKernelKingsState;
  private turnTimer: ReturnType<typeof setTimeout> | null = null;
  private disconnectTimers: Map<string, ReturnType<typeof setTimeout>> = new Map();
  /** Re-broadcast state every 2s until first move, in case game:state was missed on start */
  private heartbeat: ReturnType<typeof setInterval> | null = null;
  private moveCount = 0;
  /** Slot number of the AI player, or null for 2-player human games */
  private aiSlot: PieceOwner | null = null;

  constructor(lobby: ILobby, mp: ReturnType<Server['of']>) {
    this.lobby = lobby;
    this.mp = mp;
    // Single-player: the human is slot 0 (red), AI is slot 1 (blue)
    if (lobby.players.length === 1) {
      this.aiSlot = 1;
      // Add a virtual AI player to the state players list
    }
    this.state = this.initState();
  }

  private initState(): IKernelKingsState {
    const humanPlayers = this.lobby.players.map((p) => ({
      slot: p.slot as PieceOwner,
      name: p.name,
      captures: 0,
    }));
    // Add AI player entry if needed
    const players = this.aiSlot !== null
      ? [...humanPlayers, { slot: this.aiSlot, name: 'AI', captures: 0 }]
      : humanPlayers;

    return {
      board: initBoard(),
      turn: 0,
      players,
      mustJump: null,
      movesSinceCapture: 0,
      capturedRed: 0,
      capturedBlue: 0,
      turnDeadline: Date.now() + TURN_TIMEOUT_MS,
    };
  }

  start(): void {
    this.broadcastState();
    this.startTurnTimer();
    // Re-send state every 2s until the first move lands (catches missed initial state)
    this.heartbeat = setInterval(() => {
      if (this.moveCount === 0) {
        this.broadcastState();
      } else {
        if (this.heartbeat !== null) clearInterval(this.heartbeat);
        this.heartbeat = null;
      }
    }, 2000);
    // If AI goes first (shouldn't happen - human is slot 0, but guard anyway)
    if (this.aiSlot !== null && this.state.turn === this.aiSlot) {
      setTimeout(() => this.doAiMove(), 800);
    }
  }

  /** Play a random legal move for the AI, including multi-jump chains. */
  private doAiMove(): void {
    if (this.aiSlot === null) return;
    if (this.state.turn !== this.aiSlot) return;

    // When mustJump is set, continue from that piece only (double/triple/quad jump chain)
    const moves = this.state.mustJump
      ? legalMoves(this.state.board, this.aiSlot, this.state.mustJump).filter((m) => m.jumped !== null)
      : legalMoves(this.state.board, this.aiSlot);

    if (!moves.length) return; // should not happen (engine already ends game if no moves)

    // Pick a random move; prefer jumps (they're mandatory anyway)
    const move = moves[Math.floor(Math.random() * moves.length)];
    this.moveCount++;
    this.applyMove(move, this.aiSlot);
  }

  stop(): void {
    this.clearTurnTimer();
    if (this.heartbeat !== null) { clearInterval(this.heartbeat); this.heartbeat = null; }
    for (const socketId of Array.from(this.disconnectTimers.keys())) {
      this.clearDisconnectTimer(socketId);
    }
  }

  // ── Moves ──────────────────────────────────────────────────────────────────

  handleMove(socketId: string, from: ICoord, to: ICoord): void {
    const player = this.lobby.players.find((p) => p.socketId === socketId);
    if (!player) return;

    const slot = player.slot as PieceOwner;
    if (slot !== this.state.turn) {
      this.sendInvalidMove(socketId, 'Not your turn.');
      return;
    }

    const piece = this.state.board[from.row]?.[from.col];
    if (!piece || piece.owner !== slot) {
      this.sendInvalidMove(socketId, 'No piece at that position.');
      return;
    }

    // If mustJump is active, the selected piece must be the jumping piece
    if (this.state.mustJump) {
      if (from.row !== this.state.mustJump.row || from.col !== this.state.mustJump.col) {
        this.sendInvalidMove(socketId, 'You must continue with the jumping piece.');
        return;
      }
    }

    // Validate the move
    const available = legalMoves(this.state.board, slot, from);
    const hasJumps = available.some((m) => m.jumped !== null);
    const move = available.find(
      (m) => m.from.row === from.row && m.from.col === from.col && m.to.row === to.row && m.to.col === to.col,
    );

    if (!move) {
      if (hasJumps) {
        this.sendInvalidMove(socketId, 'Must jump!');
      } else {
        this.sendInvalidMove(socketId, 'Invalid move.');
      }
      return;
    }

    // Apply move
    this.moveCount++;
    this.applyMove(move, slot);
  }

  private applyMove(move: IMove, slot: PieceOwner): void {
    const board = this.state.board;
    const piece = board[move.from.row][move.from.col]!;

    board[move.to.row][move.to.col] = piece;
    board[move.from.row][move.from.col] = null;

    let captured = false;
    if (move.jumped) {
      board[move.jumped.row][move.jumped.col] = null;
      captured = true;
      this.state.movesSinceCapture = 0;
      if (slot === 0) {
        this.state.capturedBlue++;
        const p = this.state.players.find((pl) => pl.slot === 0);
        if (p) p.captures++;
      } else {
        this.state.capturedRed++;
        const p = this.state.players.find((pl) => pl.slot === 1);
        if (p) p.captures++;
      }
    } else {
      this.state.movesSinceCapture++;
    }

    // King promotion: piece reaches opponent's back rank
    if (slot === 0 && move.to.row === 7) piece.king = true;
    if (slot === 1 && move.to.row === 0) piece.king = true;

    // Check for multi-jump continuation
    if (captured) {
      const furtherJumps = legalMoves(board, slot, move.to).filter((m) => m.jumped !== null);
      if (furtherJumps.length > 0) {
        this.state.mustJump = move.to;
        this.broadcastState();
        this.resetTurnTimer(); // same player, reset timer
        // If it's the AI's turn, schedule the next jump in the chain
        if (this.aiSlot !== null && slot === this.aiSlot) {
          setTimeout(() => this.doAiMove(), 600);
        }
        return;
      }
    }

    this.state.mustJump = null;

    // Check win/draw conditions before switching turn
    if (this.checkWinCondition(slot)) return;
    if (this.state.movesSinceCapture >= DRAW_MOVE_LIMIT) {
      this.endGame(null, 'draw');
      return;
    }

    // Switch turn
    this.state.turn = slot === 0 ? 1 : 0;
    this.state.turnDeadline = Date.now() + TURN_TIMEOUT_MS;
    this.broadcastState();
    this.resetTurnTimer();

    // Schedule AI move if it's now the AI's turn
    if (this.aiSlot !== null && this.state.turn === this.aiSlot) {
      setTimeout(() => this.doAiMove(), 600);
    }
  }

  private checkWinCondition(lastMover: PieceOwner): boolean {
    const opponent = lastMover === 0 ? 1 : 0;
    const board = this.state.board;

    let opponentPieces = 0;
    for (let r = 0; r < 8; r++) {
      for (let c = 0; c < 8; c++) {
        if (board[r][c]?.owner === opponent) opponentPieces++;
      }
    }

    if (opponentPieces === 0) {
      this.endGame(lastMover, 'capture_all');
      return true;
    }

    const opponentMoves = legalMoves(board, opponent);
    if (opponentMoves.length === 0) {
      this.endGame(lastMover, 'no_moves');
      return true;
    }

    return false;
  }

  // ── Timer ──────────────────────────────────────────────────────────────────

  private startTurnTimer(): void {
    this.clearTurnTimer();
    this.turnTimer = setTimeout(() => {
      const loser = this.state.turn;
      const winner = loser === 0 ? 1 : 0;
      this.endGame(winner as PieceOwner, 'timeout');
    }, TURN_TIMEOUT_MS);
  }

  private resetTurnTimer(): void {
    this.startTurnTimer();
  }

  private clearTurnTimer(): void {
    if (this.turnTimer !== null) {
      clearTimeout(this.turnTimer);
      this.turnTimer = null;
    }
  }

  // ── Disconnect ─────────────────────────────────────────────────────────────

  handleDisconnect(socketId: string): void {
    const player = this.lobby.players.find((p) => p.socketId === socketId);
    if (!player) return;

    const slot = player.slot as PieceOwner;

    const timer = setTimeout(() => {
      const winner = slot === 0 ? 1 : 0;
      this.endGame(winner as PieceOwner, 'disconnect');
    }, DISCONNECT_GRACE_MS);

    this.disconnectTimers.set(socketId, timer);
  }

  private clearDisconnectTimer(socketId: string): void {
    const timer = this.disconnectTimers.get(socketId);
    if (timer !== undefined) {
      clearTimeout(timer);
      this.disconnectTimers.delete(socketId);
    }
  }

  // ── End game ───────────────────────────────────────────────────────────────

  private endGame(winner: PieceOwner | null, reason: 'capture_all' | 'no_moves' | 'draw' | 'timeout' | 'disconnect'): void {
    this.clearTurnTimer();
    if (this.heartbeat !== null) { clearInterval(this.heartbeat); this.heartbeat = null; }
    for (const socketId of this.disconnectTimers.keys()) {
      this.clearDisconnectTimer(socketId);
    }

    this.lobby.status = 'finished';

    this.mp.to(`lobby:${this.lobby.lobbyId}`).emit('game:over', {
      winner,
      reason,
      players: this.state.players,
    });
  }

  // ── Broadcast ─────────────────────────────────────────────────────────────

  private broadcastState(): void {
    this.mp.to(`lobby:${this.lobby.lobbyId}`).emit('game:state', this.state);
  }

  private sendInvalidMove(socketId: string, reason: string): void {
    const socket = this.mp.sockets.get(socketId);
    if (socket) {
      socket.emit('game:invalid_move', { reason });
    }
  }
}
