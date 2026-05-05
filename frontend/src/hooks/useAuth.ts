import { useState, useEffect, useCallback } from 'react';
import { checkCode } from '../api/client';

const STORAGE_KEY = 'docfmt_redeem_code';

export function useAuth() {
  const [code, setCodeState] = useState<string>(() => {
    return localStorage.getItem(STORAGE_KEY) || '';
  });
  const [remaining, setRemaining] = useState<number | null>(null);
  const [valid, setValid] = useState<boolean>(false);
  const [checking, setChecking] = useState(false);

  const setCode = useCallback((newCode: string) => {
    setCodeState(newCode);
    if (newCode) {
      localStorage.setItem(STORAGE_KEY, newCode);
    } else {
      localStorage.removeItem(STORAGE_KEY);
    }
  }, []);

  const verify = useCallback(async () => {
    if (!code) {
      setValid(false);
      setRemaining(null);
      return;
    }
    setChecking(true);
    try {
      const result = await checkCode(code);
      setValid(result.valid);
      setRemaining(result.remaining);
    } catch {
      setValid(false);
      setRemaining(null);
    } finally {
      setChecking(false);
    }
  }, [code]);

  useEffect(() => {
    if (code) verify();
  }, [code, verify]);

  return { code, setCode, valid, remaining, checking, verify };
}
