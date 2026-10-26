import express from 'express';
import http from 'http';
import { Server as SocketIOServer } from 'socket.io';
import cors from 'cors';
import { TaskQueueService } from './queue';
import { ChangeStreamRelay } from './changeStream';
import { createTasksRouter } from './routes/tasks';
import { createApprovalsRouter } from './routes/approvals';

const app = express();
const server = http.createServer(app);
const io = new SocketIOServer(server, {
  cors: {
    origin: '*',
    methods: ['GET', 'POST']
  }
});

const PORT = process.env.GATEWAY_PORT || 3000;

app.use(cors());
app.use(express.json());

const queueService = new TaskQueueService();
const changeStreamRelay = new ChangeStreamRelay(io);

// Wire API routes
app.use('/api/tasks', createTasksRouter(queueService, changeStreamRelay));
app.use('/api/approvals', createApprovalsRouter(queueService, changeStreamRelay));

app.post('/api/reset', async (req, res) => {
  const ERP_URL = process.env.ERP_BASE_URL || 'http://localhost:4000';
  const RUNTIME_URL = process.env.RUNTIME_URL || 'http://localhost:8000';

  try {
    // Reset ERP database & faults
    const erpReq = http.request(`${ERP_URL}/__reset`, { method: 'POST', headers: { 'Content-Type': 'application/json' } });
    erpReq.write('{}');
    erpReq.end();

    // Reset Runtime state & locks
    const rtReq = http.request(`${RUNTIME_URL}/reset`, { method: 'POST', headers: { 'Content-Type': 'application/json' } });
    rtReq.write('{}');
    rtReq.end();

    // Clear gateway in-memory deduplication cache
    queueService.clearDedup();

    io.emit('task:reset', { timestamp: new Date().toISOString() });
    res.json({ status: 'ok', message: 'ERP, Runtime, and Gateway state successfully reset' });
  } catch (err: any) {
    res.status(500).json({ error: 'Failed to reset state', details: err.message });
  }
});

app.get('/health', (req, res) => {
  res.json({
    status: 'ok',
    service: 'centra-gateway',
    timestamp: new Date().toISOString()
  });
});

// Robust Error Handling Middleware
app.use((err: any, req: express.Request, res: express.Response, next: express.NextFunction) => {
  console.error('[Gateway Error]', err.message);
  if (err instanceof SyntaxError && 'body' in err) {
    return res.status(400).json({ error: 'Malformed JSON payload' });
  }
  res.status(500).json({ error: err.message || 'Internal Server Error' });
});

process.on('uncaughtException', (err) => {
  console.error('[Uncaught Exception]', err.message);
});

process.on('unhandledRejection', (reason) => {
  console.error('[Unhandled Rejection]', reason);
});

io.on('connection', (socket) => {
  console.log(`[Socket.IO] Client connected: ${socket.id}`);
  socket.on('disconnect', () => {
    console.log(`[Socket.IO] Client disconnected: ${socket.id}`);
  });
});

server.listen(PORT, () => {
  console.log(`[CentraGateway] Ingress API & WebSocket Relay listening on http://localhost:${PORT}`);
});
