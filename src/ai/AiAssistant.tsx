import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { create } from 'zustand';
import { api, type AiAnswer } from '../api';
import { useQuery, useSession } from '../lib/hooks';
import { Px } from '../ui/Px';
import { Tracker } from '../ui/kit';
import { journeyIndex } from '../lib/status';

type Size = 'window' | 'full';
interface Msg {
  id: number;
  me: boolean;
  text: string;
  quote?: string;
  answer?: AiAnswer;
  error?: boolean;
}

interface AiState {
  open: boolean;
  size: Size;
  width: number;
  screen: string;
  appId?: string;
  chips: string[];
  tip?: { text: string; action?: string };
  tipHidden: boolean;
  msgs: Msg[];
  busy: boolean;
  set: (p: Partial<AiState>) => void;
}

export const useAi = create<AiState>((set) => ({
  open: false,
  size: 'window',
  width: (() => {
    try {
      return Number(localStorage.getItem('ai-width')) || 420;
    } catch {
      return 420;
    }
  })(),
  screen: 'Главная',
  chips: [],
  tipHidden: false,
  msgs: [],
  busy: false,
  set: (p) => set(p),
}));

/** Страница сообщает помощнику, где находится человек */
export function useAiScreen(screen: string, opts: { appId?: string; chips?: string[]; tip?: { text: string; action?: string } } = {}) {
  const set = useAi((s) => s.set);
  const key = `${screen}|${opts.appId}|${opts.tip?.text}|${(opts.chips ?? []).join(',')}`;
  useEffect(() => {
    set({ screen, appId: opts.appId, chips: opts.chips ?? [], tip: opts.tip, tipHidden: false });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
}

let mid = 1;

export async function askAi(question: string, selection?: string) {
  const st = useAi.getState();
  const session = useSession.getState().session;
  if (!session) return;
  const shown = question === '__steps__' ? 'Что мне делать дальше?' : question;
  st.set({ open: true, busy: true, msgs: [...st.msgs, { id: mid++, me: true, text: shown, quote: selection }] });
  try {
    const a = await api.askAi(session, { screen: st.screen, appId: st.appId, selection }, question);
    const s2 = useAi.getState();
    s2.set({ busy: false, msgs: [...s2.msgs, { id: mid++, me: false, text: a.ok ? a.text : a.error ?? 'Ошибка', answer: a, error: !a.ok }] });
  } catch (e) {
    const s2 = useAi.getState();
    s2.set({ busy: false, msgs: [...s2.msgs, { id: mid++, me: false, text: 'Помощник временно недоступен. Это не мешает заявке — все шаги можно пройти без него.', error: true }] });
  }
}

export function AiAssistant() {
  const s = useAi();
  const session = useSession((x) => x.session);
  const nav = useNavigate();
  const [q, setQ] = useState('');
  const body = useRef<HTMLDivElement>(null);
  const app = useQuery(() => (s.appId && session ? api.getApplication(session, s.appId) : Promise.resolve(undefined)), [s.appId, session?.userId]);

  useEffect(() => {
    body.current?.scrollTo({ top: body.current.scrollHeight, behavior: 'smooth' });
  }, [s.msgs.length, s.busy]);

  useEffect(() => {
    if (!s.open) return;
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && s.set({ open: false });
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [s.open, s]);

  const startResize = (e: React.PointerEvent) => {
    e.preventDefault();
    const startX = e.clientX;
    const startW = s.width;
    const move = (ev: PointerEvent) => {
      const w = Math.max(360, Math.min(720, startW + (startX - ev.clientX)));
      useAi.getState().set({ width: w });
    };
    const up = () => {
      window.removeEventListener('pointermove', move);
      window.removeEventListener('pointerup', up);
      try {
        localStorage.setItem('ai-width', String(useAi.getState().width));
      } catch {
        /* ignore */
      }
    };
    window.addEventListener('pointermove', move);
    window.addEventListener('pointerup', up);
  };

  const send = () => {
    const t = q.trim();
    if (!t || s.busy) return;
    setQ('');
    askAi(t);
  };

  return (
    <>
      {!s.open && (
        <>
          {s.tip && !s.tipHidden && (
            <div className="ai-bubble" role="status">
              <span>{s.tip.text}</span>
              <div className="row-c" style={{ gap: 14 }}>
                {s.tip.action && (
                  <button type="button" className="linkbtn" style={{ color: 'var(--c-ai-ink)' }} onClick={() => askAi(s.tip!.action!)}>
                    {s.tip.action}
                  </button>
                )}
                <button type="button" className="linkbtn muted" onClick={() => s.set({ tipHidden: true })}>
                  Скрыть
                </button>
              </div>
            </div>
          )}
          <button type="button" className="ai-fab" aria-label="Открыть ИИ-помощника" onClick={() => s.set({ open: true, tipHidden: true })}>
            <Px name="gem" size={28} color="var(--c-lime)" />
          </button>
        </>
      )}
      {s.open && (
        <section className={`ai-win ${s.size === 'full' ? 'full' : ''}`} style={{ width: s.size === 'full' ? Math.max(s.width, 560) : s.width }} aria-label="ИИ-помощник">
          <header className="ai-head">
            {s.size !== 'full' && (
              <span className="ai-resize" onPointerDown={startResize} title="Потяните, чтобы изменить ширину" aria-hidden="true">
                <svg width="18" height="18" viewBox="0 0 6 6" shapeRendering="crispEdges">
                  <path d="M0 0h4v1h-4zM0 1h1v3h-1z" fill="#C6F432" />
                </svg>
              </span>
            )}
            <span style={{ width: 40, height: 40, borderRadius: 12, background: 'rgba(255,255,255,.14)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <Px name="gem" size={20} color="var(--c-lime)" />
            </span>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div className="t">ИИ-помощник</div>
              <div className="s">Объясняет по данным заявки · решений не принимает</div>
            </div>
            <button type="button" onClick={() => s.set({ size: s.size === 'full' ? 'window' : 'full' })} aria-label={s.size === 'full' ? 'Свернуть в окно' : 'Развернуть'} title={s.size === 'full' ? 'Свернуть в окно' : 'Развернуть'}>
              {s.size === 'full' ? '⤡' : '⤢'}
            </button>
            <button type="button" onClick={() => s.set({ open: false })} aria-label="Закрыть помощника">
              ✕
            </button>
          </header>
          <div className="ai-path">
            <span className="xs" style={{ fontWeight: 700, color: 'var(--c-ai-ink)' }}>
              Ваш путь к кредиту
            </span>
            <Tracker index={journeyIndex(app.data?.status)} labels={['Шансы', 'Заявка', 'Проверка', 'Решение', 'Подпись', 'Выдача']} />
            <button type="button" className="linkbtn" style={{ alignSelf: 'flex-start', color: 'var(--c-ai-ink)' }} onClick={() => askAi('__steps__')}>
              Что мне делать дальше?
            </button>
          </div>
          <div className="ai-body" ref={body}>
            {s.msgs.length === 0 && (
              <div className="msg bot">
                Привет! Я объясню термины, статус заявки и решение банка простыми словами. Можно выделить любой текст на странице и нажать «Спросить ИИ».
              </div>
            )}
            {s.msgs.map((m) => (
              <div key={m.id} className={`msg ${m.me ? 'me' : 'bot'} ${m.error ? 'err' : ''}`}>
                {m.quote && <span className="quote">Выделенный текст: «{m.quote.slice(0, 80)}»</span>}
                {m.text}
                {!m.me && m.answer?.sources && m.answer.sources.length > 0 && (
                  <span className="ai-src" style={{ display: 'block', marginTop: 8 }}>
                    Источник: {m.answer.sources.map((x) => `${x.name}${x.asOf ? `, на ${x.asOf}` : ''}`).join('; ')}
                  </span>
                )}
                {!m.me && m.answer?.actions && m.answer.actions.length > 0 && (
                  <span className="row-c" style={{ marginTop: 8 }}>
                    {m.answer.actions.map((a) => (
                      <button key={a.to} type="button" className="linkbtn" style={{ color: 'var(--c-ai-ink)' }} onClick={() => nav(a.to)}>
                        {a.label} →
                      </button>
                    ))}
                  </span>
                )}
              </div>
            ))}
            {s.busy && (
              <div className="msg bot" aria-live="polite">
                <span className="spin" style={{ width: 14, height: 14, marginRight: 8 }} /> Думаю…
              </div>
            )}
          </div>
          {s.chips.length > 0 && (
            <div className="ai-chips">
              {s.chips.map((c) => (
                <button key={c} type="button" onClick={() => askAi(c)} disabled={s.busy}>
                  {c}
                </button>
              ))}
            </div>
          )}
          <form
            className="ai-input"
            onSubmit={(e) => {
              e.preventDefault();
              send();
            }}
          >
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Спросите что угодно о кредите" aria-label="Вопрос помощнику" />
            <button type="submit" aria-label="Отправить" disabled={s.busy}>
              →
            </button>
          </form>
        </section>
      )}
    </>
  );
}
