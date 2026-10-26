import { Router, Request, Response } from 'express';
import { TaskQueueService } from '../queue';
import { ChangeStreamRelay } from '../changeStream';

export function createApprovalsRouter(queue: TaskQueueService, relay: ChangeStreamRelay): Router {
  const router = Router();

  router.post('/', async (req: Request, res: Response) => {
    const { taskId, approved, note } = req.body;
    if (!taskId) {
      return res.status(400).json({ error: 'taskId is required' });
    }

    relay.broadcastTaskUpdate(taskId, 'APPROVAL_SUBMITTED', { approved, note });

    try {
      const result = await queue.resumeInRuntime(taskId, Boolean(approved), note);
      if (Array.isArray(result.history)) {
        for (const h of result.history) {
          relay.broadcastTaskUpdate(taskId, (h.type || 'GRAPH_STEP').toUpperCase(), h);
        }
      }
      relay.broadcastTaskUpdate(taskId, result.status, result);
      res.json({
        taskId,
        status: result.status,
        result
      });
    } catch (err: any) {
      res.status(500).json({ error: 'Failed to resume runtime execution', details: err.message });
    }
  });

  return router;
}
