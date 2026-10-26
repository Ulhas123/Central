import { Server as SocketIOServer } from 'socket.io';
import { EventEmitter } from 'events';

export class ChangeStreamRelay extends EventEmitter {
  constructor(private io: SocketIOServer) {
    super();
  }

  broadcastTaskUpdate(taskId: string, eventType: string, payload: any) {
    this.io.emit('task:update', {
      taskId,
      eventType,
      payload,
      timestamp: new Date().toISOString()
    });
  }

  broadcastInterruptRequested(taskId: string, interruptData: any) {
    this.io.emit('hitl:interrupt', {
      taskId,
      interruptData,
      timestamp: new Date().toISOString()
    });
  }
}
