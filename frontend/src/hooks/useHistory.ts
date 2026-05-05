import { useState, useCallback } from 'react';
import type { HistoryItem } from '../types';

const STORAGE_KEY = 'docfmt_history';
const MAX_ITEMS = 100;

function load(): HistoryItem[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function save(items: HistoryItem[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(items.slice(0, MAX_ITEMS)));
}

export function useHistory() {
  const [items, setItems] = useState<HistoryItem[]>(load);

  const add = useCallback((item: HistoryItem) => {
    setItems((prev) => {
      const next = [item, ...prev].slice(0, MAX_ITEMS);
      save(next);
      return next;
    });
  }, []);

  const remove = useCallback((id: string) => {
    setItems((prev) => {
      const next = prev.filter((h) => h.id !== id);
      save(next);
      return next;
    });
  }, []);

  const clear = useCallback(() => {
    setItems([]);
    localStorage.removeItem(STORAGE_KEY);
  }, []);

  return { items, add, remove, clear };
}
