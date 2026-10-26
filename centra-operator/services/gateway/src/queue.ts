import crypto from 'crypto';
import http from 'http';

const RUNTIME_URL = process.env.RUNTIME_URL || 'http://localhost:8000';

export interface TaskJobData {
  taskId: string;
  goal: string;
  companyId: string;
}

// In-Memory Fallback Queue & Deduplication
const dedupCache = new Map<string, number>();

export class TaskQueueService {
  private redisConnected = false;

  constructor() {
    // Attempt optional Redis connection
  }

  generateFingerprint(goal: string, companyId: string): string {
    const normalized = `${companyId.trim().toUpperCase()}:${goal.trim().toLowerCase()}`;
    return crypto.createHash('sha256').update(normalized).digest('hex');
  }

  isDuplicate(fingerprint: string, ttlSeconds = 5): boolean {
    const now = Date.now();
    const existing = dedupCache.get(fingerprint);
    if (existing && now < existing) {
      return true; // Duplicate!
    }
    dedupCache.set(fingerprint, now + (ttlSeconds * 1000));
    return false;
  }

  clearDedup(): void {
    dedupCache.clear();
  }

  async dispatchToRuntime(jobData: TaskJobData): Promise<any> {
    return new Promise((resolve, reject) => {
      const payload = JSON.stringify({
        goal: jobData.goal,
        company_id: jobData.companyId,
        task_id: jobData.taskId
      });

      const url = new URL(`${RUNTIME_URL}/runs`);
      const req = http.request(
        {
          hostname: url.hostname,
          port: url.port,
          path: url.pathname,
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Content-Length': Buffer.byteLength(payload)
          }
        },
        (res) => {
          let data = '';
          res.on('data', (chunk) => { data += chunk; });
          res.on('end', () => {
            try {
              resolve(JSON.parse(data));
            } catch (err) {
              resolve({ raw: data, status: res.statusCode });
            }
          });
        }
      );

      req.on('error', (err) => reject(err));
      req.write(payload);
      req.end();
    });
  }

  async resumeInRuntime(taskId: string, approved: boolean, note?: string): Promise<any> {
    return new Promise((resolve, reject) => {
      const payload = JSON.stringify({
        task_id: taskId,
        approved,
        note
      });

      const url = new URL(`${RUNTIME_URL}/resume`);
      const req = http.request(
        {
          hostname: url.hostname,
          port: url.port,
          path: url.pathname,
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Content-Length': Buffer.byteLength(payload)
          }
        },
        (res) => {
          let data = '';
          res.on('data', (chunk) => { data += chunk; });
          res.on('end', () => {
            try {
              resolve(JSON.parse(data));
            } catch (err) {
              resolve({ raw: data, status: res.statusCode });
            }
          });
        }
      );

      req.on('error', (err) => reject(err));
      req.write(payload);
      req.end();
    });
  }
}
