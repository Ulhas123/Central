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

app.get('/health', (req, res) => {
  res.json({
    status: 'ok',
    service: 'centra-gateway',
    timestamp: new Date().toISOString()
  });
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
