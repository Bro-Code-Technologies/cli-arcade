// Dev mock...
type ConnectionType = 'multiplayer';

class CliaPresenceTracker {
  addConnection(type: ConnectionType): void {
    // left blank for dev server
    // Devs need to call these still for multiplayer connections.
  }

  removeConnection(type: ConnectionType): void {
    // left blank for dev server
    // Devs need to call these still for multiplayer connections.
  }

  gameStarted(lobbyId: string, gameType: string, playerCount: number): void {
    // left blank for dev server
    // Devs need to call these still for multiplayer connections.
  }

  gameEnded(lobbyId: string): void {
    // left blank for dev server
    // Devs need to call these still for multiplayer connections.
  }

  gamePlayerCountChanged(lobbyId: string, count: number): void {
    // left blank for dev server
    // Devs need to call these still for multiplayer connections.
  }
}

export const cliaPresenceTracker = new CliaPresenceTracker();
