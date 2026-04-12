import express from 'express';
import http from 'http';
import { initializeSockets } from './sockets/index';
import scoreRoutes from './controllers/scores.controller';

const app = express();

app.use(express.json());

app.get('/health', async (req, res) => {
  res.json({ status: 'ok' });
});

app.use('/api/apps/cli-arcade', scoreRoutes);

const httpPort = 8000;
const httpServer = http.createServer(app);

initializeSockets(httpServer, {} as any);
httpServer.listen(httpPort, () => {
  console.log(`HTTP server listening on port ${httpPort}`);
  console.log(`Run: $env:CLI_ARCADE_API_URL = "http://localhost:${httpPort}"`);
});
