import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { api, type SourceMode, type SourceState } from '../../api';
import { useAction, useQuery } from '../../lib/hooks';
import { time } from '../../lib/format';
import { Btn, Chip, Confirm, ErrorState, Loading, PageTitle, Toggle, toast } from '../../ui/kit';

const MODES: { m: SourceMode; label: string }[] = [
  { m: 'SUCCESS', label: 'Работает' },
  { m: 'SLOW', label: 'Медленно' },
  { m: 'TIMEOUT', label: 'Таймаут' },
  { m: 'ERROR', label: 'Ошибка' },
];

const SCENARIOS = [
  { id: 'auto_approve', title: 'Компания A — одобрение без участия банка', mark: 'var(--c-high)' },
  { id: 'counter', title: 'Компания C — запрос выписки → встречное предложение', mark: 'var(--c-mid)' },
  { id: 'decline', title: 'Компания E — отказ по стоп-фактору', mark: 'var(--c-negative)' },
  { id: 'docs', title: 'Компания D — не хватает данных → документы', mark: 'var(--c-attention)' },
  { id: 'source_fail', title: 'БКИ падает → заявка ждёт и продолжает сама', mark: 'var(--c-ai)' },
] as const;

export function Simulator() {
  const nav = useNavigate();
  const sources = useQuery(() => api.getSources(), []);
  const log = useQuery(() => api.getSimLog(), []);
  const [reset, setReset] = useState(false);
  const run = useAction(async (_k, id: (typeof SCENARIOS)[number]['id']) => {
    const appId = await api.runScenario(id);
    toast('Заявка создана и отправлена');
    nav(`/demo/mirror?app=${appId}`);
  });
  const doReset = useAction(async () => {
    await api.resetDemo();
    setReset(false);
    toast('Демо-данные сброшены');
  });

  return (
    <>
      <PageTitle title="Пульт внешних источников" right={<Btn view="outlined" onClick={() => setReset(true)}>Сбросить демо-данные</Btn>} />
      <p style={{ margin: 0, maxWidth: 760 }}>Сломайте любой источник и посмотрите: заявка не получает ложный отказ, а ждёт и продолжает сама, когда источник вернётся. Здесь же — сбои подписи, выдачи и ИИ-помощника.</p>
      {sources.error && <ErrorState error={sources.error} onRetry={() => sources.reload()} />}
      {!sources.data ? (
        <Loading lines={4} />
      ) : (
        <div className="grid-3" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(min(280px, 100%), 1fr))', gap: 16 }}>
          {sources.data.map((s) => (
            <SourceCard key={s.id} s={s} onChange={(v) => sources.setData(v)} />
          ))}
        </div>
      )}
      <div className="row">
        <section className="card grow" style={{ background: 'var(--c-black)', color: '#fff' }}>
          <h2 className="h2">Сценарии демо</h2>
          <span className="small" style={{ color: '#babbc2' }}>
            Создают свежую заявку от имени владельца и сразу отправляют. Откроется режим зеркала.
          </span>
          <div className="stack-s">
            {SCENARIOS.map((sc) => (
              <button
                key={sc.id}
                type="button"
                onClick={() => run.run(sc.id)}
                disabled={run.pending}
                style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, minHeight: 52, padding: '0 16px', border: 0, borderRadius: 12, background: '#3f3f45', color: '#fff', cursor: 'pointer', textAlign: 'left' }}
              >
                <span>{sc.title}</span>
                <span style={{ width: 12, height: 12, background: sc.mark, flex: 'none' }} />
              </button>
            ))}
          </div>
          {run.error && <ErrorState error={run.error} />}
          <Link to="/demo/mirror" style={{ color: '#fff' }}>
            Открыть режим зеркала →
          </Link>
        </section>
        <section className="card side">
          <h2 className="h2">Что происходит</h2>
          <ul className="feed">
            {(log.data ?? []).slice(0, 14).map((e) => (
              <li key={e.id}>
                <span className="t">{time(e.at)}</span>
                <span className="dot" style={{ background: e.text.includes('TIMEOUT') || e.text.includes('ERROR') ? 'var(--c-ai)' : 'var(--c-high)' }} />
                <span>{e.text}</span>
              </li>
            ))}
          </ul>
        </section>
      </div>
      <Confirm
        open={reset}
        title="Сбросить демо-данные?"
        text="Все созданные заявки удалятся, источники вернутся в режим «Работает». Тестовые компании и аккаунты останутся."
        confirm="Сбросить"
        danger
        pending={doReset.pending}
        onConfirm={() => doReset.run()}
        onClose={() => setReset(false)}
      />
    </>
  );
}

function SourceCard({ s, onChange }: { s: SourceState; onChange: (v: SourceState[]) => void }) {
  const bad = s.enabled && (s.mode === 'TIMEOUT' || s.mode === 'ERROR');
  const set = async (patch: Partial<Pick<SourceState, 'enabled' | 'mode'>>) => {
    const v = await api.setSource(s.id, patch);
    onChange(v);
  };
  return (
    <section className={`src-card ${bad ? 'bad' : ''} ${!s.enabled ? 'off' : ''}`}>
      <div className="row-c between" style={{ flexWrap: 'nowrap', alignItems: 'flex-start' }}>
        <div>
          <b>{s.name}</b>
          <div className="xs muted">{s.description}</div>
        </div>
        <Toggle checked={s.enabled} onChange={(v) => set({ enabled: v })} label={<span className="sr-only">Включён</span>} />
      </div>
      <div className="seg" role="group" aria-label={`Режим: ${s.name}`} style={{ flexWrap: 'wrap' }}>
        {MODES.map((m) => (
          <button key={m.m} type="button" aria-pressed={s.mode === m.m} disabled={!s.enabled} onClick={() => set({ mode: m.m })} style={s.mode === m.m && (m.m === 'TIMEOUT' || m.m === 'ERROR') ? { background: 'var(--c-ai)' } : undefined}>
            {m.label}
          </button>
        ))}
      </div>
      <span className="xs" style={{ color: bad ? 'var(--c-ai-ink)' : 'var(--c-text-2)', fontWeight: bad ? 600 : 400 }}>
        {!s.enabled ? 'Выключен — запросы падают с ошибкой' : s.lastCall ? `Последний ответ ${time(s.lastCall.at)} · ${s.lastCall.result}` : 'Запросов ещё не было'}
      </span>
      {s.affected && s.affected.length > 0 && (
        <div className="row-c">
          <span className="xs">Ждут:</span>
          {s.affected.map((a) => (
            <Link key={a.id} to={`/demo/mirror?app=${a.id}`}>
              <Chip kind="mid">№ {a.number}</Chip>
            </Link>
          ))}
        </div>
      )}
    </section>
  );
}
