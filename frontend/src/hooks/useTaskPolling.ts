import { useState, useRef, useCallback, useEffect } from 'react';
import { pollTask } from '../api/client';
import type { TaskInfo } from '../types';

const FAST_INTERVAL = 800;
const NORMAL_INTERVAL = 2000;
const FAST_DURATION_MS = 30_000;

export function useTaskPolling() {
  const [task, setTask] = useState<TaskInfo | null>(null);
  const [polling, setPolling] = useState(false);
  const [startedAt, setStartedAt] = useState<number | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const startedAtRef = useRef<number>(0);
  const intervalRef = useRef(FAST_INTERVAL);

  const start = useCallback((taskId: string) => {
    setPolling(true);
    setTask(null);
    const now = Date.now();
    startedAtRef.current = now;
    setStartedAt(now);

    const poll = async () => {
      try {
        const data = await pollTask(taskId);
        setTask(data);

        if (data.status === 'completed' || data.status === 'failed') {
          stop();
          return;
        }

        // Adaptive polling: fast for first 30s, then normal
        const elapsed = Date.now() - startedAtRef.current;
        const nextInterval = elapsed < FAST_DURATION_MS ? FAST_INTERVAL : NORMAL_INTERVAL;
        if (nextInterval !== intervalRef.current) {
          intervalRef.current = nextInterval;
          if (timerRef.current) {
            clearInterval(timerRef.current);
            timerRef.current = setInterval(poll, nextInterval);
          }
        }
      } catch {
        // ignore transient errors
      }
    };

    poll();
    timerRef.current = setInterval(poll, FAST_INTERVAL);
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

  return { task, polling, startedAt, start, stop };
}
