import React, { createContext, useContext, useState, useCallback } from 'react';
import type { TaskInfo } from '../types';

interface FormatSessionState {
  // File
  file: File | null;
  setFile: (f: File | null) => void;
  // Template
  tplMode: 'builtin' | 'upload' | 'nl';
  setTplMode: (m: 'builtin' | 'upload' | 'nl') => void;
  tplId: number | undefined;
  setTplId: (id: number | undefined) => void;
  tplFile: File | null;
  setTplFile: (f: File | null) => void;
  tplDesc: string;
  setTplDesc: (d: string) => void;
  // Task
  task: TaskInfo | null;
  setTask: (t: TaskInfo | null) => void;
  polling: boolean;
  setPolling: (p: boolean) => void;
  startedAt: number | null;
  setStartedAt: (t: number | null) => void;
  done: boolean;
  setDone: (d: boolean) => void;
  error: string;
  setError: (e: string) => void;
  showPreview: boolean;
  setShowPreview: (s: boolean) => void;
  // Reset
  reset: () => void;
}

const FormatSessionContext = createContext<FormatSessionState | null>(null);

export function FormatSessionProvider({ children }: { children: React.ReactNode }) {
  const [file, setFile] = useState<File | null>(null);
  const [tplMode, setTplMode] = useState<'builtin' | 'upload' | 'nl'>('builtin');
  const [tplId, setTplId] = useState<number | undefined>();
  const [tplFile, setTplFile] = useState<File | null>(null);
  const [tplDesc, setTplDesc] = useState('');
  const [task, setTask] = useState<TaskInfo | null>(null);
  const [polling, setPolling] = useState(false);
  const [startedAt, setStartedAt] = useState<number | null>(null);
  const [done, setDone] = useState(false);
  const [error, setError] = useState('');
  const [showPreview, setShowPreview] = useState(false);

  const reset = useCallback(() => {
    setFile(null);
    setTplFile(null);
    setTplDesc('');
    setError('');
    setDone(false);
    setShowPreview(false);
    setTask(null);
    setPolling(false);
    setStartedAt(null);
  }, []);

  return (
    <FormatSessionContext.Provider value={{
      file, setFile,
      tplMode, setTplMode,
      tplId, setTplId,
      tplFile, setTplFile,
      tplDesc, setTplDesc,
      task, setTask,
      polling, setPolling,
      startedAt, setStartedAt,
      done, setDone,
      error, setError,
      showPreview, setShowPreview,
      reset,
    }}>
      {children}
    </FormatSessionContext.Provider>
  );
}

export function useFormatSession() {
  const ctx = useContext(FormatSessionContext);
  if (!ctx) throw new Error('useFormatSession must be used within FormatSessionProvider');
  return ctx;
}
