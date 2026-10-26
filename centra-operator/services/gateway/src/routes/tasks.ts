import { Router, Request, Response } from 'express';
import { TaskQueueService } from '../queue';
import { ChangeStreamRelay } from '../changeStream';
import http from 'http';

export function createTasksRouter(queue: TaskQueueService, relay: ChangeStreamRelay): Router {
  const router = Router();
  const RUNTIME_URL = process.env.RUNTIME_URL || 'http://localhost:8000';

  router.post('/', async (req: Request, res: Response) => {
    const { goal, company_id } = req.body;
    if (!goal) {
      return res.status(400).json({ error: 'Goal prompt is required' });
    }

    const companyId = company_id || 'COMP-001';
    const fingerprint = queue.generateFingerprint(goal, companyId);

    // Idempotency / Deduplication Guard
    if (queue.isDuplicate(fingerprint)) {
      return res.status(409).json({
        error: 'Duplicate task submission rejected by idempotency filter',
        fingerprint
      });
    }

    const taskId = `task_${Date.now()}_${Math.random().toString(36).substring(2, 6)}`;
    relay.broadcastTaskUpdate(taskId, 'TASK_ENQUEUED', { goal, companyId });

    try {
      const result = await queue.dispatchToRuntime({
        taskId,
        goal,
        companyId
      });

      if (result.status === 'AWAITING_APPROVAL') {
        relay.broadcastInterruptRequested(taskId, result.interrupt_data);
      } else {
        relay.broadcastTaskUpdate(taskId, result.status, result);
      }

      res.status(202).json({
        taskId,
        status: result.status,
        result
      });
    } catch (err: any) {
      relay.broadcastTaskUpdate(taskId, 'TASK_FAILED', { error: err.message });
      res.status(500).json({ error: 'Runtime dispatch error', details: err.message });
    }
  });

  router.get('/:id', (req: Request, res: Response) => {
    const taskId = req.params.id;
    const url = new URL(`${RUNTIME_URL}/tasks/${taskId}/status`);

    const clientReq = http.get(url, (clientRes) => {
      let data = '';
      clientRes.on('data', chunk => data += chunk);
      clientRes.on('end', () => {
        try {
          res.status(clientRes.statusCode || 200).json(JSON.parse(data));
        } catch {
          res.status(clientRes.statusCode || 200).send(data);
        }
      });
    });

    clientReq.on('error', (err) => {
      res.status(500).json({ error: 'Failed to contact agent runtime', details: err.message });
    });
  });

  return router;
}
