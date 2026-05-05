import { useState, useRef, useCallback, useEffect } from 'react';
import { pollTask } from '../api/client';
import type { TaskInfo, ClassificationItem } from '../types';

export function useTaskPolling() {
  const [task, setTask] = useState<TaskInfo | null>(null);
  const [polling, setPolling] = useState(false);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const start = useCallback((taskId: string) => {
    setPolling(true);
    setTask(null);

    const poll = async () => {
      try {
        const data = await pollTask(taskId);
        setTask(data);

        if (data.status === 'completed' || data.status === 'failed') {
          stop();
        }
      } catch {
        // ignore transient errors
      }
    };

    poll();
    timerRef.current = setInterval(poll, 1200);
  }, []);

  const stop = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    setPolling(false);
  }, []);

  useEffect(() => {
    return () => stop();
  }, [stop]);

  return { task, polling, start, stop };
}
