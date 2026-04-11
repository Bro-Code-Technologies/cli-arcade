import express from 'express';
import http from 'http';
import { initializeSockets } from './sockets/index';

const app = express();

app.get('/health', async (req, res) => {
  res.json({ status: 'ok' });
});

const httpPort = 8000;
const httpServer = http.createServer(app);

initializeSockets(httpServer, {});
httpServer.listen(httpPort, () => {
  console.log(`HTTP server listening on port ${httpPort}`);
  console.log(`Run $env:CLI_ARCADE_API_URL = "http://localhost:${httpPort}"`);
});
