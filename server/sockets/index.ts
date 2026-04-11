import { Server } from 'socket.io';
import http from 'http';
import https from 'https';
import { registerCliArcadeMultiplayer } from './sockets/cli-arcade-mp.socket';

let io: Server | null = null;

export const getIo = (): Server | null => io;

export const initializeSockets = (
  server: http.Server | https.Server,
  corsOrigin?: string | string[],
): void => {
  const origin = corsOrigin || '*';

  io = new Server(server, {
    cors: {
      origin,
      methods: ['GET', 'POST'],
      credentials: true,
    },
  });

  // Register namespaces / handlers
  registerCliArcadeMultiplayer(io);

  console.log('Sockets initialized');
};
