import { Server } from 'socket.io';
import { ILobby, IStarShip2State, ISSPlayer } from '../../cli-arcade-mp.interfaces';
import { cliaPresenceTracker } from '../../clia-presence.tracker';

const TICK_MS = 100; // 10 Hz
const STAR_VALUE = 10;
const SPECIAL_BASE_VALUE = 50;
const INITIAL_SHIP_LENGTH = 3;

export class StarShip2Engine {
  private lobby: ILobby;
  private mp: ReturnType<Server['of']>;
  private arenaWidth: number;
  private arenaHeight: number;
  private state: IStarShip2State;
  private inputBuffer: Map<string, [number, number]>;
  private interval: ReturnType<typeof setInterval> | null = null;
  private tick = 0;
  private nextSpecialAt: number;
  private specialExpireAt: number | null = null;

  private startingPlayerCount: number;

  constructor(lobby: ILobby, mp: ReturnType<Server['of']>, arenaWidth: number, arenaHeight: number) {
    this.lobby = lobby;
    this.mp = mp;
    this.arenaWidth = arenaWidth;
    this.arenaHeight = arenaHeight;
    this.inputBuffer = new Map();
    this.nextSpecialAt = Date.now() + this.randomSpecialInterval();
    this.startingPlayerCount = lobby.players.length;
    this.state = this.initState();
  }

  // ── Initialization ─────────────────────────────────────────────────────────

  private initState(): IStarShip2State {
    const players: ISSPlayer[] = this.lobby.players.map((p, idx) => ({
      slot: p.slot,
      name: p.name,
      alive: true,
      score: 0,
      ship: this.spawnShip(idx, this.lobby.players.length),
      direction: [0, 1],
    }));

    const state: IStarShip2State = {
      tick: 0,
      players,
      stars: [],
      specialStar: null,
      arenaWidth: this.arenaWidth,
      arenaHeight: this.arenaHeight,
    };

    // Place initial stars
    for (let i = 0; i < Math.min(3, players.length + 1); i++) {
      this.placeStar(state);
    }

    return state;
  }

  private spawnShip(idx: number, total: number): Array<{ row: number; col: number }> {
    // Place ships evenly spaced around the arena
    const positions: Array<{ row: number; col: number }> = [
      { row: Math.floor(this.arenaHeight * 0.25), col: Math.floor(this.arenaWidth * 0.25) },
      { row: Math.floor(this.arenaHeight * 0.25), col: Math.floor(this.arenaWidth * 0.75) },
      { row: Math.floor(this.arenaHeight * 0.75), col: Math.floor(this.arenaWidth * 0.25) },
      { row: Math.floor(this.arenaHeight * 0.75), col: Math.floor(this.arenaWidth * 0.75) },
    ];

    const head = positions[idx % positions.length];
    const ship = [];
    for (let i = 0; i < INITIAL_SHIP_LENGTH; i++) {
      ship.push({ row: head.row, col: Math.max(0, head.col - i) });
    }
    return ship;
  }

  // ── Game loop ──────────────────────────────────────────────────────────────

  start(): void {
    this.interval = setInterval(() => this.tickEngine(), TICK_MS);
  }

  stop(): void {
    if (this.interval !== null) {
      clearInterval(this.interval);
      this.interval = null;
    }
  }

  private tickEngine(): void {
    const aliveBefore = this.state.players.filter((p) => p.alive).length;
    if (aliveBefore === 0) {
      this.endGame();
      return;
    }

    this.tick++;
    this.state.tick = this.tick;
    const now = Date.now();

    // Handle special star expiry
    if (this.state.specialStar && this.specialExpireAt !== null && now > this.specialExpireAt) {
      this.state.specialStar = null;
      this.specialExpireAt = null;
    }

    // Maybe spawn a special star
    if (!this.state.specialStar && now >= this.nextSpecialAt) {
      this.placeSpecial(this.state);
    }

    // Process all inputs and move ships
    const occupiedByBodies = new Set<string>();
    for (const player of this.state.players) {
      if (!player.alive) continue;
      // Tail cells (not including head) are occupied
      for (let i = 1; i < player.ship.length; i++) {
        occupiedByBodies.add(this.coordKey(player.ship[i]));
      }
    }

    const newHeads: Map<number, { row: number; col: number }> = new Map();

    for (const player of this.state.players) {
      if (!player.alive) continue;

      // Get latest buffered direction
      const socketId = this.lobby.players.find((p) => p.slot === player.slot)?.socketId;
      if (socketId) {
        const buffered = this.inputBuffer.get(socketId);
        if (buffered) {
          // Prevent 180-degree reversal
          const [dy, dx] = buffered;
          const [cdy, cdx] = player.direction;
          if (!(dy === -cdy && dx === -cdx && (dy !== 0 || dx !== 0))) {
            player.direction = buffered;
          }
          this.inputBuffer.delete(socketId);
        }
      }

      const [dy, dx] = player.direction;
      const head = player.ship[0];
      newHeads.set(player.slot, { row: head.row + dy, col: head.col + dx });
    }

    // Detect deaths
    const dying = new Set<number>();

    for (const [slot, head] of newHeads) {
      // Wall collision
      if (head.row < 0 || head.row >= this.arenaHeight || head.col < 0 || head.col >= this.arenaWidth) {
        dying.add(slot);
        this.emitPlayerDied(slot, 'wall');
      }
      // Body collision (against existing bodies at tick start)
      else if (occupiedByBodies.has(this.coordKey(head))) {
        dying.add(slot);
        this.emitPlayerDied(slot, 'self');
      }
    }

    // Head-to-head collision
    const headArray = Array.from(newHeads.entries());
    for (let i = 0; i < headArray.length; i++) {
      for (let j = i + 1; j < headArray.length; j++) {
        const [slotA, headA] = headArray[i];
        const [slotB, headB] = headArray[j];
        if (
          !dying.has(slotA) && !dying.has(slotB) &&
          headA.row === headB.row && headA.col === headB.col
        ) {
          dying.add(slotA);
          dying.add(slotB);
          this.emitPlayerDied(slotA, 'collision');
          this.emitPlayerDied(slotB, 'collision');
        }
      }
    }

    // Move surviving ships
    for (const player of this.state.players) {
      if (!player.alive || dying.has(player.slot)) continue;

      const head = newHeads.get(player.slot)!;
      let grew = false;

      // Check star collection
      const starIdx = this.state.stars.findIndex((s) => s.row === head.row && s.col === head.col && !s.special);
      if (starIdx !== -1) {
        this.state.stars.splice(starIdx, 1);
        player.score += STAR_VALUE;
        grew = true;
        this.placeStar(this.state);
      }

      // Check special star
      const sp = this.state.specialStar;
      if (sp && sp.row === head.row && sp.col === head.col && sp.special) {
        const bonus = SPECIAL_BASE_VALUE * (this.state.stars.length + 1);
        player.score += bonus;
        grew = true;
        this.state.specialStar = null;
        this.specialExpireAt = null;
        this.nextSpecialAt = now + this.randomSpecialInterval();
      }

      player.ship.unshift(head);
      if (!grew) {
        player.ship.pop();
      }
    }

    // Mark dead players
    for (const slot of dying) {
      const player = this.state.players.find((p) => p.slot === slot);
      if (player) {
        player.alive = false;
        player.ship = [];
      }
    }

    // Broadcast state
    this.mp.to(`lobby:${this.lobby.lobbyId}`).emit('game:state', this.state);

    // Check end condition — solo game ends only when the single player dies
    const aliveNow = this.state.players.filter((p) => p.alive).length;
    if (this.startingPlayerCount === 1 ? aliveNow < 1 : aliveNow <= 1) {
      this.endGame();
    }
  }

  // ── Inputs ─────────────────────────────────────────────────────────────────

  handleInput(socketId: string, direction: [number, number]): void {
    this.inputBuffer.set(socketId, direction);
  }

  handleDisconnect(socketId: string): void {
    // Mark the disconnected player's ship as dead immediately so the game
    // can detect end-of-game on the next tick rather than waiting for the
    // ghost ship to drift into something (which could take 10+ minutes).
    const player = this.state.players.find(
      (p) => this.lobby.players.find((lp) => lp.slot === p.slot)?.socketId === socketId,
    );
    if (player && player.alive) {
      player.alive = false;
      this.emitPlayerDied(player.slot, 'wall');
    }
  }

  // ── Star placement ─────────────────────────────────────────────────────────

  private placeStar(state: IStarShip2State): void {
    const occupied = new Set<string>();
    for (const p of state.players) {
      for (const c of p.ship) occupied.add(this.coordKey(c));
    }
    for (const s of state.stars) occupied.add(this.coordKey(s));
    if (state.specialStar) occupied.add(this.coordKey(state.specialStar));

    for (let attempt = 0; attempt < 2000; attempt++) {
      const row = Math.floor(Math.random() * this.arenaHeight);
      const col = Math.floor(Math.random() * this.arenaWidth);
      const key = this.coordKey({ row, col });
      if (!occupied.has(key)) {
        state.stars.push({ row, col, special: false });
        return;
      }
    }
  }

  private placeSpecial(state: IStarShip2State): void {
    const occupied = new Set<string>();
    for (const p of state.players) {
      for (const c of p.ship) occupied.add(this.coordKey(c));
    }
    for (const s of state.stars) occupied.add(this.coordKey(s));

    for (let attempt = 0; attempt < 2000; attempt++) {
      const row = Math.floor(Math.random() * this.arenaHeight);
      const col = Math.floor(Math.random() * this.arenaWidth);
      const key = this.coordKey({ row, col });
      if (!occupied.has(key)) {
        state.specialStar = { row, col, special: true };
        const lifetime = (this.arenaWidth + this.arenaHeight) * 35; // ms
        this.specialExpireAt = Date.now() + Math.max(5000, Math.min(30000, lifetime));
        return;
      }
    }
  }

  // ── End game ───────────────────────────────────────────────────────────────

  private endGame(): void {
    this.stop();
    const rankings = this.state.players
      .slice()
      .sort((a, b) => b.score - a.score)
      .map((p) => ({ slot: p.slot, name: p.name, score: p.score, alive: p.alive }));

    this.mp.to(`lobby:${this.lobby.lobbyId}`).emit('game:over', { rankings });
    this.lobby.status = 'finished';
    cliaPresenceTracker.gameEnded(this.lobby.lobbyId);
  }

  private emitPlayerDied(slot: number, cause: 'wall' | 'self' | 'collision'): void {
    this.mp.to(`lobby:${this.lobby.lobbyId}`).emit('game:player_died', { slot, cause });
  }

  // ── Utilities ──────────────────────────────────────────────────────────────

  private coordKey(c: { row: number; col: number }): string {
    return `${c.row},${c.col}`;
  }

  private randomSpecialInterval(): number {
    return (8 + Math.random() * 10) * 1000; // 8-18 seconds in ms
  }
}
