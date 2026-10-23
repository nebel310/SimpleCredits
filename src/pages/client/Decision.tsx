import { useState } from 'react';
import { Navigate, useNavigate, useParams } from 'react-router-dom';
import { api } from '../../api';
import { productByCode } from '../../api/catalog';
import { useAction, useSession } from '../../lib/hooks';
import { date, dateTime, dec2, money } from '../../lib/format';
import { monthlyLoad } from '../../lib/calc';
import { PRODUCT_NAME } from '../../lib/status';
import { Btn, Chip, Confirm, ErrorState, Loading, PageTitle, RoleGuard, toast } from '../../ui/kit';
import { Px } from '../../ui/Px';
import { useAiScreen } from '../../ai/AiAssistant';
import { useApp } from './Applications';

export function Decision() {
  const { id } = useParams();
  const { session, user } = useSession();
  const nav = useNavigate();
  const q = useApp(id);
  const app = q.data;
  const [mode, setMode] = useState<'plain' | 'bank'>('plain');
  const [rejectOpen, setRejectOpen] = useState(false);
  const [wa, setWa] = useState<number | null>(null);
  const [wt, setWt] = useState<number | null>(null);

  const accept = useAction(async (key) => {
    const v = await api.acceptOffer(session!, id!, app!.offer!.id, app!.offer!.version, key);
    toast('Предложение принято. Осталось подписать договор');
    nav(`/applications/${v.id}/sign`);
  });
  const reject = useAction(async (key) => {
    await api.rejectOffer(session!, id!, app!.offer!.id, key);
    setRejectOpen(false);
  });

  useAiScreen('Решение банка', { appId: id, chips: ['Почему условия изменились?', 'Почему отказ?', 'Что будет, если отказаться?', 'Сколько я переплачу?'], tip: app?.offer?.kind === 'counter' ? { text: 'Объясню, почему банк предложил другую сумму и что будет, если согласиться.', action: 'Почему условия изменились?' } : undefined });

  if (q.error) return <ErrorState error={q.error} onRetry={() => q.reload()} />;
  if (!app) return <Loading lines={6} />;
  const st = app.status;
  if (!['OFFER', 'DECLINED', 'EXPIRED', 'OFFER_REJECTED', 'SIGNING', 'DISBURSEMENT', 'ACTIVE'].includes(st) || !app.decision) return <Navigate to={`/applications/${app.id}`} replace />;

  const d = app.decision;
  const o = app.offer;
  const kind = st === 'EXPIRED' ? 'expired' : d.outcome === 'DECLINE' ? 'decline' : o?.kind === 'counter' ? 'counter' : 'approve';
  const decidedBy = d.by === 'system' ? 'автоматически по правилам' : d.by === 'committee' ? 'кредитным комитетом' : 'сотрудником банка';
  const chip = kind === 'approve' ? <Chip kind="high">Одобрено</Chip> : kind === 'counter' ? <Chip kind="mid">Банк предлагает другие условия</Chip> : kind === 'expired' ? <Chip kind="neutral">Предложение истекло</Chip> : <Chip kind="low">Не одобрено</Chip>;
  const title =
    kind === 'approve'
      ? `Одобрено: ${money(o!.amount)} на ${o!.termMonths} мес`
      : kind === 'counter'
        ? `Можем дать ${money(o!.amount)} вместо ${money(o!.requested.amount)}`
        : kind === 'expired'
          ? 'Срок действия предложения истёк'
          : 'Банк не может выдать кредит по текущим данным';
  const icon = kind === 'decline' || kind === 'expired' ? 'alert' : 'check';
  const iconColor = kind === 'approve' ? 'var(--c-high)' : kind === 'counter' ? 'var(--c-mid)' : 'var(--c-negative)';
  const offerOpen = st === 'OFFER';

  // «Что если?» — предварительный расчёт на месте
  const prod = o ? productByCode(o.product) : null;
  const amount = wa ?? o?.amount ?? 0;
  const term = wt ?? o?.termMonths ?? 12;
  const pay = o && prod ? monthlyLoad(o.product, amount, term) : 0;
  const cf = app.afford?.cashFlow ?? 0;
  const cur = app.afford?.currentPayments ?? 0;
  const rest = cf - cur - pay;
  const ratio = cf ? (cur + pay) / cf : 0;

  return (
    <>
      <PageTitle crumbs={`Заявки › № ${app.number} › Решение`} title="Решение по заявке" />
      <section className="hero dark">
        <div style={{ flex: '1 1 560px', minWidth: 0 }}>
          {chip}
          <h2 style={{ fontSize: 30, marginTop: 12, textWrap: 'balance' as never }}>{title}</h2>
          <div className="small" style={{ marginTop: 14, color: 'rgba(255,255,255,.72)' }}>
            Решение № {d.id.toUpperCase()} · {dateTime(d.at)} · принято {decidedBy}
            {o && offerOpen && ` · предложение действует до ${date(o.validUntil)}`}
            {o && kind === 'expired' && ` · действовало до ${date(o.validUntil)}`}
          </div>
        </div>
        <Px name={icon} size={84} color={iconColor} />
      </section>

      {st === 'OFFER_REJECTED' && <div className="info-box">Вы отказались от этого предложения. Можно подать новую заявку на главной.</div>}
      {['SIGNING', 'DISBURSEMENT', 'ACTIVE'].includes(st) && <div className="info-box">Вы приняли это предложение {dateTime(o?.acceptedAt)} (версия {o?.version}). {st === 'SIGNING' ? 'Осталось подписать договор.' : ''}</div>}

      <div className="row">
        <div className="grow stack">
          {o && kind !== 'decline' && (
            <section className="card">
              <h2 className="h2">{kind === 'counter' ? 'Вы запросили и что предлагаем' : 'Условия'}</h2>
              <div className="tbl-wrap">
                <table className="tbl">
                  <thead>
                    <tr>
                      <th />
                      {kind === 'counter' && <th>Вы запросили</th>}
                      <th style={{ color: 'var(--c-text)' }}>{kind === 'counter' ? 'Предлагаем' : 'Одобрено'}</th>
                    </tr>
                  </thead>
                  <tbody>
                    <Row label="Продукт" a={kind === 'counter' ? PRODUCT_NAME[o.requested.product] : undefined} b={PRODUCT_NAME[o.product]} />
                    <Row label={prod!.kind === 'limit' ? 'Лимит' : 'Сумма'} a={kind === 'counter' ? money(o.requested.amount) : undefined} b={<b className="num">{money(o.amount)}</b>} strike />
                    <Row label="Срок" a={kind === 'counter' ? `${o.requested.termMonths} мес` : undefined} b={`${o.termMonths} мес`} />
                    <Row label="Ставка" a={kind === 'counter' ? `${productByCode(o.requested.product).ratePct}% годовых` : undefined} b={`${o.ratePct}% годовых${prod!.kind === 'limit' ? ' за дни использования' : ''}`} />
                    {prod!.kind === 'loan' && <Row label="Платёж в месяц" a={kind === 'counter' ? money(monthlyLoad(o.requested.product, o.requested.amount, o.requested.termMonths)) : undefined} b={<b>{money(o.monthlyPayment)}</b>} />}
                    <Row label={prod!.kind === 'limit' ? 'Стоимость при 50% использования' : 'Переплата за весь срок'} b={money(o.overpayment)} a={kind === 'counter' ? '—' : undefined} />
                    {o.fees.map((f) => (
                      <Row key={f.name} label={`Обязательный платёж: ${f.name.toLowerCase()}`} b={money(f.amount)} a={kind === 'counter' ? '—' : undefined} />
                    ))}
                    <Row label="Обеспечение" b={o.collateral} a={kind === 'counter' ? '—' : undefined} />
                    <Row label="Поручитель" b={o.guarantor} a={kind === 'counter' ? '—' : undefined} />
                  </tbody>
                </table>
              </div>
              {o.product !== o.requested.product && (
                <div className="warn-box">
                  Банк предлагает другой продукт: {PRODUCT_NAME[o.product]} вместо «{PRODUCT_NAME[o.requested.product]}». {prod!.suits}.
                </div>
              )}
              <span className="xs muted">Ставки и комиссии — модельные, для прототипа. Версия предложения: {o.version}.</span>
            </section>
          )}

          {o && offerOpen && prod && (
            <section className="card">
              <div className="row-c between">
                <h2 className="h2">Что если?</h2>
                <span className="xs muted">Предварительный расчёт — предложение банка не меняется</span>
              </div>
              <div className="grid-fields">
                <label className="field">
                  <span className="lbl row-c between" style={{ display: 'flex' }}>
                    <span>{prod.kind === 'limit' ? 'Лимит' : 'Сумма'}</span>
                    <span>{money(amount)}</span>
                  </span>
                  <input type="range" min={prod.amountMin} max={Math.max(o.requested.amount, o.amount)} step={100000} value={amount} onChange={(e) => setWa(Number(e.target.value))} style={{ accentColor: 'var(--c-black)', width: '100%' }} />
                </label>
                <label className="field">
                  <span className="lbl" style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span>Срок</span>
                    <span>{term} мес</span>
                  </span>
                  <input type="range" min={prod.termMin} max={prod.termMax} step={1} value={term} onChange={(e) => setWt(Number(e.target.value))} style={{ accentColor: 'var(--c-black)', width: '100%' }} />
                </label>
              </div>
              {app.afford && (
                <div className="stack-s">
                  <div className="row-c between small">
                    <b>Запас прочности</b>
                    <Chip kind={ratio <= 0.66 ? 'high' : ratio <= 0.77 ? 'attention' : 'low'}>{ratio <= 0.66 ? 'Хватает' : ratio <= 0.77 ? 'На грани' : 'Слишком мало'}</Chip>
                  </div>
                  <div aria-hidden="true" style={{ display: 'flex', height: 28, gap: 2 }}>
                    <span style={{ width: `${Math.min(100, (cur / cf) * 100)}%`, background: 'var(--c-gray)' }} />
                    <span style={{ width: `${Math.min(100, (pay / cf) * 100)}%`, background: 'var(--c-black)' }} />
                    {rest > 0 && <span style={{ width: `${(rest / cf) * 100}%`, background: 'var(--c-high)' }} />}
                  </div>
                  <div className="row-c xs" style={{ gap: '6px 18px' }}>
                    <span className="row-c" style={{ gap: 6 }}>
                      <i style={{ width: 10, height: 10, background: 'var(--c-gray)' }} />
                      Текущие кредиты {money(cur)}
                    </span>
                    <span className="row-c" style={{ gap: 6 }}>
                      <i style={{ width: 10, height: 10, background: 'var(--c-black)' }} />
                      {prod.kind === 'limit' ? 'Проценты по лимиту' : 'Новый платёж'} {money(pay)}
                    </span>
                    <span className="row-c" style={{ gap: 6 }}>
                      <i style={{ width: 10, height: 10, background: 'var(--c-high)' }} />
                      <b>Остаётся {money(Math.max(0, rest))}</b>
                    </span>
                  </div>
                  <span className="xs muted">Из денежного потока {money(cf)} в месяц по выписке. Банку нужен запас не меньше 1,3 — сейчас {dec2(cf / (cur + pay || 1))}.</span>
                </div>
              )}
            </section>
          )}

          {offerOpen && o && (
            <section className="card">
              <RoleGuard allowed={app.permissions.acceptOffer} role={user!.role} what="Принять предложение">
                <div className="btn-row">
                  <Btn view="accent" onClick={() => accept.run()} loading={accept.pending}>
                    Принять {money(o.amount)}
                  </Btn>
                  <button type="button" className="linkbtn muted" onClick={() => setRejectOpen(true)}>
                    Отказаться
                  </button>
                </div>
                <span className="xs muted">
                  Принимаете версию {o.version} предложения. Договор подпишете на следующем шаге. Предложение действует до {date(o.validUntil)}.
                </span>
              </RoleGuard>
              {accept.error && <ErrorState error={accept.error} onRetry={() => (accept.error?.code === 'conflict' ? q.reload() : accept.run())} />}
            </section>
          )}

          {(kind === 'decline' || kind === 'expired' || st === 'OFFER_REJECTED') && (
            <section className="card">
              <h2 className="h2">Что можно сделать</h2>
              <ol style={{ margin: 0, paddingLeft: 20, display: 'flex', flexDirection: 'column', gap: 8 }}>
                {(kind === 'decline' ? d.advice : ['Подать новую заявку — данные компании подтянем снова']).map((a) => (
                  <li key={a}>{a}</li>
                ))}
              </ol>
              <div className="btn-row">
                <Btn view="primary" to="/home">
                  Посмотреть шансы на главной
                </Btn>
              </div>
            </section>
          )}
        </div>

        <aside className="side stack">
          <section className="ai-hint">
            <div className="row-c between">
              <div className="ttl">
                <Px name="gem" size={18} color="var(--c-ai)" />
                Разбор от ИИ
              </div>
              <div className="seg seg-sm" role="group" aria-label="Формулировки" style={{ background: '#fff' }}>
                <button type="button" aria-pressed={mode === 'plain'} onClick={() => setMode('plain')}>
                  Простыми словами
                </button>
                <button type="button" aria-pressed={mode === 'bank'} onClick={() => setMode('bank')}>
                  Как в банке
                </button>
              </div>
            </div>
            <p>{d.clientText}</p>
            {d.reasons.length > 0 && (
              <ul style={{ margin: 0, paddingLeft: 0, listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 8 }}>
                {d.reasons.map((r) => (
                  <li key={r.code} className="row-c" style={{ flexWrap: 'nowrap', alignItems: 'flex-start', gap: 10 }}>
                    <Px name="alert" size={14} color="var(--c-negative)" />
                    <span className="small">{mode === 'plain' ? r.plain : r.bank}</span>
                  </li>
                ))}
              </ul>
            )}
            <span className="ai-src">Решение принял банк. ИИ только объясняет его по данным заявки № {app.number}.</span>
          </section>
          {kind === 'counter' && o && app.afford && (
            <section className="card tight">
              <h2 className="h3">Почему эта сумма</h2>
              <span className="small">
                При {money(o.requested.amount)} платёж был бы {money(monthlyLoad(o.requested.product, o.requested.amount, o.requested.termMonths))} — денег бизнеса на него не хватает с нужным запасом. При {money(o.amount)} платёж {money(o.monthlyPayment)}, после всех кредитов остаётся {money(app.afford.cashFlow - app.afford.currentPayments - o.monthlyPayment)} в месяц.
              </span>
            </section>
          )}
        </aside>
      </div>

      <Confirm
        open={rejectOpen}
        title="Отказаться от предложения?"
        text={<span>Заявка закроется. Позже можно подать новую — условия посчитаем заново.{reject.error && <span className="err" style={{ display: 'block' }}>{reject.error.message}</span>}</span>}
        confirm="Отказаться"
        danger
        pending={reject.pending}
        onConfirm={() => reject.run()}
        onClose={() => setRejectOpen(false)}
      />
    </>
  );
}

function Row({ label, a, b, strike }: { label: string; a?: React.ReactNode; b: React.ReactNode; strike?: boolean }) {
  return (
    <tr>
      <td className="muted">{label}</td>
      {a !== undefined && <td style={strike ? { textDecoration: 'line-through', color: 'var(--c-text-2)' } : undefined}>{a}</td>}
      <td>{b}</td>
    </tr>
  );
}
