// Dev mock...
import { Socket } from 'socket.io';

export const socketAuth = (socket: Socket, next: (err?: Error) => void): void => {
  // left blank for dev server
  // Devs need to call these still for multiplayer connections.
  next();
};
