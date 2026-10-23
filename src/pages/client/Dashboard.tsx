import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, type ProductChance, type ProductCode } from '../../api';
import { useAction, useQuery, useSession } from '../../lib/hooks';
import { dateTime, money, ago } from '../../lib/format';
import { PRODUCT_NAME, statusMeta } from '../../lib/status';
import { AiHint, Btn, Chip, Confirm, ErrorState, LEVEL, Loading, Meter, toast } from '../../ui/kit';
import { Px } from '../../ui/Px';
import { useAiScreen } from '../../ai/AiAssistant';
import { PRODUCTS } from '../../api/catalog';

export function Dashboard() {
  const { session, user } = useSession();
  const nav = useNavigate();
  const [refreshing, setRefreshing] = useState(false);
  const [how, setHow] = useState(false);
  const [agree, setAgree] = useState(false);
  const chances = useQuery(() => api.getChances(session!, user!.companyId!), [user?.companyId]);
  const apps = useQuery(() => api.listApplications(session!), [session?.userId]);
  const consent = useAction(async () => {
    await api.giveBkiConsent(session!, user!.companyId!);
    toast('Согласие сохранено. Пересчитываем оценку');
  });

  const c = chances.data;
  const active = apps.data?.find((a) => !['DRAFT', 'DECLINED', 'CANCELLED', 'OFFER_REJECTED', 'EXPIRED', 'REPAID'].includes(a.status));
  const draft = apps.data?.find((a) => a.status === 'DRAFT');
  const best = c?.products.filter((p) => p.pct !== null).sort((a, b) => (b.pct ?? 0) - (a.pct ?? 0))[0];
  const neg = c?.factors.find((f) => f.dir === '-');

  useAiScreen('Главная: шансы на кредит', {
    chips: ['Почему такой шанс?', 'Что такое овердрафт?', 'Какую сумму выбрать?', 'Какие документы понадобятся?'],
    tip: c
      ? c.state === 'insufficient'
        ? { text: 'Бизнесу меньше полугода, отчётности ещё нет. Расскажу, что поможет банку оценить вас уже сейчас.', action: 'Почему такой шанс?' }
        : neg
          ? { text: `${neg.name}: ${neg.note}. Объяснить, как это влияет на оценку?`, action: 'Почему такой шанс?' }
          : { text: 'Подскажу, какую сумму комфортно взять по вашим оборотам.', action: 'Какую сумму выбрать?' }
      : undefined,
  });

  const refresh = async () => {
    setRefreshing(true);
    try {
      const r = await api.getChances(session!, user!.companyId!, { refresh: true });
      chances.setData(r);
      if (r.state === 'error') toast(r.error ?? 'Не удалось обновить', true);
    } finally {
      setRefreshing(false);
    }
  };

  const start = (p: ProductCode, ch?: ProductChance) => {
    const prod = PRODUCTS.find((x) => x.code === p)!;
    const amount = ch?.limit ? Math.min(ch.limit, prod.amountMax) : prod.amountMin;
    nav(`/apply/goal?product=${p}&amount=${amount}`);
  };

  if (chances.loading && !c) return <Loading lines={5} />;
  if (chances.error && !c) return <ErrorState error={chances.error} onRetry={() => chances.reload()} />;
  if (!c) return null;

  const allBlocked = c.products.every((p) => p.level === 'blocked');
  const heroTitle =
    c.state === 'insufficient'
      ? 'Пока не хватает данных для оценки'
      : allBlocked
        ? 'Сейчас кредит недоступен — есть стоп-фактор'
        : best
          ? `Предварительно подходит: ${PRODUCT_NAME[best.product].toLowerCase()}`
          : 'Ваши шансы на кредит';

  return (
    <>
      <section className="hero">
        <div style={{ flex: '1 1 560px', minWidth: 0 }}>
          <Chip kind="lime">Шансы на финансирование</Chip>
          <h1 style={{ fontSize: 36, marginTop: 14 }}>{heroTitle}</h1>
          <p>
            {c.state === 'insufficient'
              ? 'Отчётности в ФНС ещё нет, а история оборотов короткая. Ниже — что поможет банку оценить ваш бизнес.'
              : c.bkiConsent
                ? 'Оценка по данным ФНС, оборотам по счёту и кредитной истории.'
                : 'Предварительно: по открытым данным ФНС и оборотам по счёту, без кредитной истории.'}
          </p>
          <div className="row-c" style={{ marginTop: 14, gap: 18 }}>
            <span className="small">
              {c.state === 'error' ? c.error : `Обновлено ${dateTime(c.calculatedAt)}`}
            </span>
            <button type="button" className="linkbtn" style={{ color: '#fff' }} onClick={refresh} disabled={refreshing}>
              {refreshing ? (
                <>
                  <span className="spin" style={{ width: 14, height: 14 }} /> Обновляем…
                </>
              ) : (
                'Обновить'
              )}
            </button>
            <button type="button" className="linkbtn" style={{ color: '#fff' }} onClick={() => setHow(true)}>
              Как мы считаем шансы
            </button>
          </div>
        </div>
        <Px name={allBlocked ? 'alert' : c.state === 'insufficient' ? 'wait' : 'heart'} size={96} color={allBlocked ? '#fff' : 'var(--c-lime)'} />
      </section>

      {active && (
        <section className="card tight" style={{ flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap' }}>
          <Px name="wait" size={28} color="var(--c-mid)" />
          <div style={{ flex: 1, minWidth: 240 }}>
            <div className="small muted">Активная заявка № {active.number}</div>
            <b>
              {PRODUCT_NAME[active.product]} · {money(active.amount)}
            </b>
          </div>
          <Chip kind={statusMeta(active as never).chipClass === 'attention' ? 'attention' : (statusMeta(active as never).chipClass as never)}>{statusMeta(active as never).chip}</Chip>
          <span className="xs muted">обновлено {ago(active.updatedAt)}</span>
          <Btn view="primary" size={40} to={`/applications/${active.id}`}>
            Открыть
          </Btn>
        </section>
      )}
      {draft && !active && (
        <section className="card tight" style={{ flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap' }}>
          <Px name="doc" size={28} color="var(--c-gray)" />
          <div style={{ flex: 1, minWidth: 240 }}>
            <div className="small muted">Черновик № {draft.number}</div>
            <b>
              {PRODUCT_NAME[draft.product]} · {money(draft.amount)}
            </b>
          </div>
          <Btn view="primary" size={40} to="/apply/goal">
            Продолжить заявку
          </Btn>
        </section>
      )}

      <div className="grid-3">
        {c.products.map((p) => (
          <ProductCard key={p.product} p={p} best={best?.product === p.product && c.state === 'ready'} onApply={() => start(p.product, p)} canApply={user!.role !== 'viewer'} />
        ))}
      </div>

      <div className="row">
        <section className="card grow">
          <div className="row-c between">
            <h2 className="h2">Что влияет на оценку</h2>
            <span className="xs muted">+ помогает · − мешает · ? нет данных</span>
          </div>
          <ul style={{ listStyle: 'none', margin: 0, padding: 0 }}>
            {c.factors.map((f) => (
              <li key={f.key} className="row-c" style={{ padding: '12px 0', borderTop: '1px solid var(--c-line)', flexWrap: 'nowrap', alignItems: 'flex-start' }}>
                <span
                  aria-label={f.dir === '+' ? 'помогает' : f.dir === '-' ? 'мешает' : 'нет данных'}
                  style={{ width: 28, height: 28, flex: 'none', display: 'flex', alignItems: 'center', justifyContent: 'center', fontWeight: 700, background: f.dir === '+' ? 'var(--c-lime)' : f.dir === '-' ? 'var(--c-red)' : 'var(--c-line)', color: f.dir === '+' ? 'var(--c-lime-ink)' : f.dir === '-' ? '#fff' : 'var(--c-text-2)' }}
                >
                  {f.dir === '-' ? '−' : f.dir}
                </span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <b>{f.name}</b> — {f.note}
                  <div className="xs muted">
                    {f.source}
                    {f.asOf ? `, данные на ${dateTime(f.asOf)}` : ''}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        </section>

        <aside className="side stack">
          <section className="card" style={{ background: 'var(--c-black)', color: '#fff' }}>
            <h2 className="h2">{c.state === 'ready' && !allBlocked ? 'Что можно сделать' : 'Как улучшить шансы'}</h2>
            <ol style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex', flexDirection: 'column', gap: 14 }}>
              {c.recommendations.map((r, i) => (
                <li key={r.id} style={{ display: 'flex', gap: 12 }}>
                  <span style={{ width: 28, height: 28, flex: 'none', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--c-lime)', color: 'var(--c-lime-ink)', fontWeight: 700 }}>{i + 1}</span>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <b>{r.title}</b>
                    <div className="small" style={{ color: '#babbc2', marginTop: 2 }}>
                      {r.text}
                    </div>
                    <div className="xs" style={{ color: 'var(--c-lime)', marginTop: 4, fontWeight: 600 }}>
                      {r.effect}
                    </div>
                    {r.action?.kind === 'consent' && (
                      <div className="stack-s" style={{ marginTop: 10, padding: 12, background: '#3f3f45', borderRadius: 12 }}>
                        {user!.role === 'owner' ? (
                          <>
                            <label className="row-c small" style={{ gap: 8, flexWrap: 'nowrap', alignItems: 'flex-start', color: '#fff' }}>
                              <input type="checkbox" checked={agree} onChange={(e) => setAgree(e.target.checked)} style={{ width: 20, height: 20, accentColor: 'var(--c-lime)' }} />
                              Согласен на запрос в бюро кредитных историй и обработку персональных данных
                            </label>
                            <Btn view="secondary" size={40} disabled={!agree} loading={consent.pending} onClick={() => consent.run()}>
                              {r.action.label}
                            </Btn>
                            {consent.error && <span className="xs" style={{ color: '#ffb3ab' }}>{consent.error.message}</span>}
                          </>
                        ) : (
                          <span className="small">Согласие даёт владелец бизнеса.</span>
                        )}
                      </div>
                    )}
                    {r.action?.kind === 'apply' && user!.role !== 'viewer' && (
                      <button type="button" className="linkbtn" style={{ color: '#fff', marginTop: 8 }} onClick={() => start(r.action!.product ?? 'working_capital', c.products.find((x) => x.product === r.action!.product))}>
                        {r.action.label} →
                      </button>
                    )}
                  </div>
                </li>
              ))}
            </ol>
          </section>
          {neg && c.state === 'ready' && (
            <AiHint source={`${neg.source}${neg.asOf ? `, на ${dateTime(neg.asOf)}` : ''}`}>
              {neg.name.toLowerCase() === 'обороты по счёту'
                ? 'Поступления на счёт упали. Если часть оборотов идёт через другой банк, приложите выписку к заявке — банк увидит полную картину.'
                : `${neg.name}: ${neg.note}. Можно спросить меня, как это влияет на оценку и что сделать.`}
            </AiHint>
          )}
        </aside>
      </div>

      <p className="xs muted" style={{ margin: 0 }}>
        Шансы — предварительная модельная оценка, не гарантия одобрения. Окончательное решение принимает банк после проверки заявки.
      </p>

      <Confirm
        open={how}
        title="Как мы считаем шансы"
        confirm="Понятно"
        cancel="Закрыть"
        onConfirm={() => setHow(false)}
        onClose={() => setHow(false)}
        text={
          <div className="stack-s small">
            <span>1. Проверяем стоп-факторы: долг перед налоговой больше 50 000 ₽, просрочка 90+ дней, крупные долги у приставов.</span>
            <span>2. Считаем баллы по 9 показателям: денежный поток, кредитная история, текущая нагрузка, стабильность оборотов, возраст бизнеса и другие.</span>
            <span>3. По баллам модель оценивает вероятность одобрения для каждого продукта и его предварительный лимит.</span>
            <span>Пороги — демонстрационные, это не настоящая кредитная политика банка.</span>
          </div>
        }
      />
    </>
  );
}

function ProductCard({ p, best, onApply, canApply }: { p: ProductChance; best: boolean; onApply: () => void; canApply: boolean }) {
  const lv = LEVEL[p.level];
  const prod = PRODUCTS.find((x) => x.code === p.product)!;
  return (
    <section className="card" style={{ justifyContent: 'space-between' }}>
      <div className="stack-s">
        <div className="row-c between">
          <span className="small muted">{prod.suits}</span>
        </div>
        <h2 className="h3">{prod.name}</h2>
        <div className="row-c">
          <Chip kind={lv.chip}>
            <Px name={lv.icon} size={12} color="currentColor" /> {lv.label}
          </Chip>
          {best && <Chip kind="dark">Предварительно подходит</Chip>}
        </div>
      </div>
      <div className="stack-s">
        <div className="row-c" style={{ alignItems: 'flex-end', gap: 14 }}>
          <span className="display" style={{ color: p.pct === null ? 'var(--c-text-3)' : undefined }}>
            {p.pct === null ? (p.level === 'unknown' ? '—' : '—') : `${p.approx ? '≈' : ''}${p.pct}%`}
          </span>
          {p.pct !== null && <Px name={lv.icon} size={36} color={lv.fill} />}
        </div>
        <Meter value={p.pct} color={lv.fill} />
        <span className="xs muted">
          {p.level === 'unknown' ? 'Не рассчитано: недостаточно данных' : p.level === 'blocked' ? 'Не рассчитано из-за стоп-фактора' : 'Предварительная модельная оценка. Не гарантия одобрения'}
        </span>
      </div>
      {p.blocker ? (
        <div className="small" style={{ color: 'var(--c-negative-ink)', fontWeight: 600 }}>
          {p.blocker}
        </div>
      ) : (
        <dl className="dl">
          <div>
            <dt>Предварительно до</dt>
            <dd>{money(p.limit)}</dd>
          </div>
          <div>
            <dt>Срок</dt>
            <dd>
              {prod.termMin}–{prod.termMax} мес
            </dd>
          </div>
          <div>
            <dt>Ставка (модельная)</dt>
            <dd>
              {prod.ratePct}% {prod.kind === 'limit' ? 'за дни использования' : 'годовых'}
            </dd>
          </div>
        </dl>
      )}
      {canApply &&
        (p.level === 'unknown' ? (
          <Btn view="outlined" onClick={onApply}>
            Дополнить данные
          </Btn>
        ) : p.level === 'blocked' ? (
          <Btn view="outlined" disabled>
            Сейчас недоступно
          </Btn>
        ) : (
          <Btn view={best ? 'accent' : 'outlined'} onClick={onApply}>
            Оформить
          </Btn>
        ))}
    </section>
  );
}
