import { useCallback, useEffect, useRef, useState } from 'react';
import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import { api, ApiError, type Session, type User } from '../api';
import { newKey } from './format';

// ───── Сессия демо-входа: хранится в sessionStorage, поэтому в разных вкладках можно войти разными ролями
interface SessionState {
  session: Session | null;
  user: User | null;
  login: (u: User) => void;
  logout: () => void;
}

const safeSession = createJSONStorage(() => {
  try {
    sessionStorage.setItem('__t', '1');
    sessionStorage.removeItem('__t');
    return sessionStorage;
  } catch {
    const mem = new Map<string, string>();
    return { getItem: (k: string) => mem.get(k) ?? null, setItem: (k: string, v: string) => void mem.set(k, v), removeItem: (k: string) => void mem.delete(k) };
  }
});

export const useSession = create<SessionState>()(
  persist(
    (set) => ({
      session: null,
      user: null,
      login: (u) => set({ session: { userId: u.id }, user: u }),
      logout: () => set({ session: null, user: null }),
    }),
    { name: 'alfa-credit-session', storage: safeSession },
  ),
);

// ───── Запрос с автообновлением по событиям сервера
export function useQuery<T>(fn: () => Promise<T>, deps: unknown[], opts: { live?: boolean } = { live: true }) {
  const [data, setData] = useState<T | undefined>(undefined);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(true);
  const fnRef = useRef(fn);
  fnRef.current = fn;
  const seq = useRef(0);

  const run = useCallback(async (silent = false) => {
    const my = ++seq.current;
    if (!silent) setLoading(true);
    try {
      const r = await fnRef.current();
      if (my === seq.current) {
        setData(r);
        setError(null);
      }
    } catch (e) {
      if (my === seq.current) setError(e instanceof ApiError ? e : new ApiError('unknown', String(e)));
    } finally {
      if (my === seq.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    run();
    if (opts.live === false) return;
    let t: ReturnType<typeof setTimeout> | null = null;
    const off = api.onChange(() => {
      if (t) clearTimeout(t);
      t = setTimeout(() => run(true), 60);
    });
    return () => {
      off();
      if (t) clearTimeout(t);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return { data, error, loading, reload: run, setData };
}

// ───── Действие: защита от двойного нажатия + ключ идемпотентности
export function useAction<A extends unknown[], R>(fn: (key: string, ...args: A) => Promise<R>) {
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const [done, setDone] = useState(false);
  const busy = useRef(false);
  const key = useRef(newKey());

  const run = useCallback(
    async (...args: A): Promise<R | undefined> => {
      if (busy.current) return undefined;
      busy.current = true;
      setPending(true);
      setError(null);
      try {
        const r = await fn(key.current, ...args);
        setDone(true);
        key.current = newKey();
        return r;
      } catch (e) {
        const err = e instanceof ApiError ? e : new ApiError('unknown', String(e));
        setError(err);
        // после ошибки, на которой действие не выполнено, новый ключ безопасен
        key.current = newKey();
        return undefined;
      } finally {
        busy.current = false;
        setPending(false);
      }
    },
    [fn],
  );

  return { run, pending, error, done, reset: () => { setError(null); setDone(false); } };
}

export function useTick(ms = 30000) {
  const [, set] = useState(0);
  useEffect(() => {
    const t = setInterval(() => set((x) => x + 1), ms);
    return () => clearInterval(t);
  }, [ms]);
}
