import { useEffect, useRef } from 'react';
import { API_URL, renewSession } from './http';
import { useSession } from './session';
import type { WsMessage } from './types';

// Один WebSocket на вкладку, пока пользователь вошёл: /ws/applications?token=<access>.
// Бэкенд шлёт события только владельцу заявки. После переподключения слушатели получают
// { type: 'reconnected' } и перечитывают данные (USERFLOW §8).

type Listener = (m: WsMessage | { type: 'reconnected' }) => void;

const listeners = new Set<Listener>();
let socket: WebSocket | null = null;
let token: string | null = null;
let retryTimer: ReturnType<typeof setTimeout> | null = null;
let attempt = 0;
let wasOpen = false;

function wsUrl(t: string) {
  const base = /^https?:/.test(API_URL) ? API_URL.replace(/^http/, 'ws') : `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}${API_URL}`;
  return `${base}/ws/applications?token=${encodeURIComponent(t)}`;
}

function emit(m: WsMessage | { type: 'reconnected' }) {
  listeners.forEach((l) => l(m));
}

function connect() {
  if (retryTimer) clearTimeout(retryTimer);
  retryTimer = null;
  socket?.close();
  socket = null;
  if (!token) return;
  const ws = new WebSocket(wsUrl(token));
  socket = ws;
  ws.onopen = () => {
    if (wasOpen || attempt > 0) emit({ type: 'reconnected' });
    wasOpen = true;
    attempt = 0;
  };
  ws.onmessage = (e) => {
    try {
      emit(JSON.parse(e.data) as WsMessage);
    } catch {
      /* не JSON — пропускаем */
    }
  };
  ws.onclose = async (e) => {
    if (socket !== ws) return;
    socket = null;
    if (!token) return;
    if (e.code === 4401) {
      // токен истёк — продлеваем сессию; с новым токеном переподключит подписка на стор ниже
      await renewSession();
      return;
    }
    attempt += 1;
    retryTimer = setTimeout(connect, Math.min(1000 * attempt, 5000));
  };
}

// Вход, выход и новый токен — переподключаемся с актуальным токеном
useSession.subscribe((s) => {
  if (s.access !== token) {
    token = s.access;
    if (!token) wasOpen = false;
    connect();
  }
});

/** Подписка на живые обновления заявок. Колбэк вызывается на каждое сообщение и после переподключения. */
export function useLiveUpdates(cb: Listener) {
  const ref = useRef(cb);
  ref.current = cb;
  useEffect(() => {
    const l: Listener = (m) => ref.current(m);
    listeners.add(l);
    if (!socket) {
      token = useSession.getState().access;
      connect();
    }
    return () => {
      listeners.delete(l);
    };
  }, []);
}
