import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import type { User } from './types';

// Сессия живёт в sessionStorage: в разных вкладках можно войти под разными аккаунтами.
interface SessionState {
  access: string | null;
  refresh: string | null;
  user: User | null;
  /** Логин и пароль демо-аккаунта: по ним сессия восстанавливается сама, если токен истёк */
  demo: { email: string; password: string } | null;
  setTokens: (access: string, refresh?: string | null) => void;
  setUser: (u: User) => void;
  setDemo: (d: { email: string; password: string } | null) => void;
  clear: () => void;
}

const storage = createJSONStorage(() => {
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
      access: null,
      refresh: null,
      user: null,
      demo: null,
      setTokens: (access, refresh) => set((s) => ({ access, refresh: refresh === undefined ? s.refresh : refresh })),
      setUser: (user) => set({ user }),
      setDemo: (demo) => set({ demo }),
      clear: () => set({ access: null, refresh: null, user: null, demo: null }),
    }),
    { name: 'simplecredits-session', storage },
  ),
);

export const profileComplete = (u: User | null) => !!(u && u.company && u.financials && u.credit_history);
