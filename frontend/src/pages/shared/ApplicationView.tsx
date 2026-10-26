import { useEffect, useState } from 'react';
import { api, type AppAction, type Application, type AppEvent, type Product } from '../../api';
import { useLiveUpdates } from '../../api/ws';
import { useAction, useQuery } from '../../lib/hooks';
import { loadProducts, productByType, productName } from '../../lib/catalog';
import { date, dateTime, money, months, pct, time } from '../../lib/format';
import { CONDITION_NAME, DECISION_NAME, FEATURE_NOT_IN_APPLICATION, factorAdvice, factorTitle, GRADE_KIND, LEGAL_FORM_NAME, POLICY_REASON, PURPOSE_NAME, SEGMENT_NAME, STATUS, eventText, outcomeText, trackIndex } from '../../lib/labels';
import { Btn, Chip, EmptyState, ErrorState, Loading, Meter, PageTitle, StatusBanner, Tracker } from '../../ui/kit';

const yesNo = (b: boolean) => (b ? 'да' : 'нет');

/** Карточка заявки: статус и следующее действие, трекер, предложение, объяснение решения, данные и история. Общая для клиента и банка */
export function ApplicationView({ id, bank }: { id: string; bank?: boolean }) {
  const q = useQuery(() => Promise.all([api.application(id), api.events(id)]), [id]);
  const products = useQuery(loadProducts, []);
  const decision = useAction(async (value: 'approve' | 'decline') => {
    await api.adminDecide(id, value);
    await q.reload(true);
  });

  // Владелец получает обновления по WebSocket; после переподключения перечитываем заявку и события
  useLiveUpdates((m) => {
    if (m.type === 'reconnected' || m.application_id === id) q.reload(true);
  });
  // Запасной вариант, пока заявка обрабатывается (и для банка, которому WebSocket не шлёт события)
  const pending = q.data?.[0].status === 'pending';
  useEffect(() => {
    if (!pending) return;
    const t = setInterval(() => q.reload(true), 2000);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pending]);

  if (q.error) return <ErrorState error={q.error.status === 404 ? 'Заявка не найдена' : q.error} onRetry={() => q.reload()} />;
  if (!q.data) return <Loading lines={6} />;
  const [a, events] = q.data;
  return <View a={a} events={events} products={products.data} bank={bank} onDecision={decision.run} decisionPending={decision.pending} decisionError={decision.error} />;
}

function View({ a, events, products, bank, onDecision, decisionPending, decisionError }: { a: Application; events: AppEvent[]; products?: Product[]; bank?: boolean; onDecision?: (value: 'approve' | 'decline') => void; decisionPending?: boolean; decisionError?: { message: string } | null }) {
  const p = a.application;
  const s = a.scoring_result;
  const dec = s?.decision;
  const name = productName(products, p.product_type);
  const meta = STATUS[a.status];
  const out = outcomeText(a, name);
  const cond = dec?.conditions ?? [];
  const reduce = cond.find((c) => c.code === 'REDUCE_AMOUNT');
  const code = productByType(products, p.product_type)?.code;
  const maxContribution = Math.max(0.0001, ...(s?.reason_codes ?? []).map((r) => Math.abs(r.contribution)));
  const advice = [...new Set((s?.reason_codes ?? [])
    .filter((r) => r.impact === 'negative')
    .map((r) => factorAdvice(r.feature))
    .filter((x): x is string => Boolean(x)))];
  const e = a.enriched_data;

  return (
    <>
      {can('retry') && (
        <Btn view="accent" onClick={() => act.run('retry')} loading={act.pending}>
          Повторить проверку
        </Btn>
      )}
      {can('accept') && (
        <Btn view="accent" onClick={() => act.run('accept')} loading={act.pending}>
          Принять предложение
        </Btn>
      )}
      {can('issue') && (
        <Btn view="accent" onClick={() => setAsk('issue')}>
          Подтвердить и оформить
        </Btn>
      )}
      {can('reject') && (
        <Btn view="outlined" onClick={() => setAsk('reject')}>
          Отказаться
        </Btn>
      )}
      {a.offer_outdated && (
        <Btn view="accent" to={`${again}&product=${o?.product_code ?? ''}`}>
          Новая заявка с теми же параметрами
        </Btn>
      )}
      {a.status === 'declined' && (
        <Btn view={noProduct(a) ? 'accent' : 'outlined'} to={noProduct(a) ? again : '/apply'}>
          {noProduct(a) ? 'Изменить параметры' : 'Новая заявка'}
        </Btn>
      )}
      {(a.status === 'rejected_by_client' || a.status === 'issued') && (
        <Btn view="outlined" to="/apply">
          Новая заявка
        </Btn>
      )}
      {act.error && !ask && <span className="small" style={{ color: 'var(--c-negative-ink)', fontWeight: 600, alignSelf: 'center' }}>{retryError}</span>}
      <Confirm
        open={ask === 'issue'}
        title="Подтвердить и оформить?"
        text={
          o ? (
            <>
              {o.product_name}: {money(o.amount_rub)} на {months(o.term_months)} под {rate(o.rate_percent)} годовых, платёж {money(o.monthly_payment_rub)} в месяц. После подтверждения оформим модельный договор — выдача синтетическая, без реальных денег.
              {act.error && <span style={{ display: 'block', marginTop: 8, color: 'var(--c-negative-ink)', fontWeight: 600 }}>{act.error.message}</span>}
            </>
          ) : (
            'Оформим кредит на условиях предложения.'
          )
        }
        confirm="Подтвердить и оформить"
        onConfirm={() => act.run('issue')}
        onClose={() => setAsk(null)}
        pending={act.pending}
      />
      <Confirm
        open={ask === 'reject'}
        title="Отказаться от предложения?"
        text={
          <>
            Заявка закроется, принять это предложение потом будет нельзя. Понадобятся деньги — подайте новую заявку.
            {act.error && <span style={{ display: 'block', marginTop: 8, color: 'var(--c-negative-ink)', fontWeight: 600 }}>{act.error.message}</span>}
          </>
        }
        confirm="Отказаться"
        cancel="Не отказываться"
        danger
        onConfirm={() => act.run('reject')}
        onClose={() => setAsk(null)}
        pending={act.pending}
      />
    </>
  );
}

function View({ a, events, products, bank, onUpdate }: { a: Application; events: AppEvent[]; products?: Product[]; bank?: boolean; onUpdate: (next: Application) => void }) {
  const p = a.application;
  const name = appTitle(a, productName(products, p.product_type));
  const d = display(a, name);
  // банку — своё пояснение к ручной проверке: решение за ним
  if (bank && a.status === 'different' && a.outcome === 'MANUAL_REVIEW') {
    d.title = 'Ждёт решения банка';
    d.text = 'Модель не приняла решение автоматически. Посмотрите оценку и данные компании и примите решение в форме ниже.';
  }
  const track = trackState(a, events);
  const e = a.enriched_data;
  const o = a.offer;
  const manual = a.status === 'different' && a.outcome === 'MANUAL_REVIEW';
  const beforeIssue = (a.status === 'confirmed' || a.status === 'different' || a.status === 'accepted') && !a.offer_outdated;
  const facts = o
    ? [
        { label: 'Сумма', value: money(o.amount_rub) },
        { label: 'Ставка', value: `${rate(o.rate_percent)} годовых` },
        { label: 'Платёж в месяц', value: money(o.monthly_payment_rub) },
      ]
    : [
        { label: 'Сумма', value: money(p.requested_amount_rub) },
        { label: 'Срок', value: months(p.term_months) },
        { label: 'Цель', value: PURPOSE_NAME[p.purpose] },
      ];

  return (
    <>
      <PageTitle
        crumbs={bank ? 'Все заявки › Заявка' : 'Заявки › Заявка'}
        title={`${name} · ${money(p.requested_amount_rub)}`}
        right={
          <span className="small muted">
            № {a.application_id.slice(0, 8)} · подана {dateTime(a.created_at)}
          </span>
        }
      />
      <StatusBanner
        kind={d.banner}
        icon={d.icon}
        chip={<Chip kind={d.kind}>{d.chip}</Chip>}
        title={d.title}
        actions={bank ? null : <ClientActions a={a} onUpdate={onUpdate} />}
        facts={facts}
      >
        <span>{d.text}</span>
        {!bank && d.next && (
          <span style={{ display: 'block', marginTop: 6, fontWeight: 600 }}>
            Что дальше: {d.next.charAt(0).toLowerCase() + d.next.slice(1)}
          </span>
        )}
      </StatusBanner>
      <Tracker index={track.index} stop={track.stop} labels={track.labels} sub={track.sub} />

      {bank && a.status === 'different' && dec?.decision === 'manual_review' && (
        <section className="card">
          <h2 className="h2">Ручное решение</h2>
          <p className="small muted" style={{ marginTop: 0 }}>
            Модель отнесла заявку к пограничной зоне. Проверьте данные и примите решение — клиент увидит его сразу в карточке и получит событие в истории.
          </p>
          <div className="btn-row">
            <Btn view="accent" loading={decisionPending} onClick={() => onDecision?.('approve')}>
              Одобрить вручную
            </Btn>
            <Btn view="outlined" loading={decisionPending} onClick={() => onDecision?.('decline')}>
              Отклонить
            </Btn>
          </div>
          {decisionError && (
            <span className="small" style={{ color: 'var(--c-negative-ink)', fontWeight: 600 }}>
              {decisionError.message}
            </span>
          )}
        </section>
      )}

      <div className="row">
        <div className="grow stack">
          {bank && manual && <BankDecisionForm a={a} onDone={onUpdate} />}
          {o && <OfferCard a={a} />}
          {!bank && o && beforeIssue && <WhatIf a={a} product={productByType(products, o.product_type)} />}
          {a.bank_decision && <BankDecisionInfo a={a} bank={bank} />}

          {bank ? <BankScoring a={a} /> : <ClientFactors a={a} />}
          {!a.scoring_result && a.status !== 'pending' && (
            <section className="card">
              <h2 className="h2">Что повлияло на оценку</h2>
              <ul className="factors">
                {s.reason_codes.map((r) => (
                  <li key={r.code}>
                    <div className="row-c between" style={{ flexWrap: 'nowrap' }}>
                      <span>
                        <b>{factorTitle(r)}</b>
                        {bank && <span className="xs muted"> · {r.feature}</span>}
                        {FEATURE_NOT_IN_APPLICATION.has(r.feature) && <span className="xs muted"> · в заявке таких данных нет, модель взяла значение по умолчанию</span>}
                      </span>
                      <Chip kind={r.impact === 'positive' ? 'high' : r.impact === 'negative' ? 'low' : 'neutral'}>{r.impact === 'positive' ? 'снижает риск' : r.impact === 'negative' ? 'повышает риск' : 'нейтрально'}</Chip>
                    </div>
                    <span className="bar" aria-hidden="true">
                      <span style={{ width: `${(Math.abs(r.contribution) / maxContribution) * 100}%`, background: r.impact === 'positive' ? 'var(--c-high)' : r.impact === 'negative' ? 'var(--c-negative)' : 'var(--c-gray)' }} />
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          )}

          {advice.length > 0 && (
            <section className="card">
              <h2 className="h2">Что можно улучшить</h2>
              <ul style={{ margin: 0, paddingLeft: 20 }}>
                {advice.map((tip) => (
                  <li key={tip} className="small">
                    {tip}
                  </li>
                ))}
              </ul>
              <span className="xs muted">Рекомендации относятся только к факторам, на которые может повлиять компания.</span>
            </section>
          )}

          {a.explanation && (
            <section className="card">
              <h2 className="h2">Комментарий модели</h2>
              <p style={{ margin: 0 }}>{a.explanation}</p>
            </section>
          )}

          {e && (
            <section className="card">
              <h2 className="h2">Данные из госисточников</h2>
              <div className="grid-3" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(min(230px, 100%), 1fr))' }}>
                <div className="panel">
                  <b>ЕГРЮЛ</b>
                  {e.egrul ? (
                    <dl className="dl stacked">
                      <div>
                        <dt>Статус</dt>
                        <dd>{e.egrul.status === 'active' ? 'действующая' : e.egrul.status}</dd>
                      </div>
                      <div>
                        <dt>Вид деятельности</dt>
                        <dd>{e.egrul.okved_description}</dd>
                      </div>
                      <div>
                        <dt>Руководитель</dt>
                        <dd>{e.egrul.director}</dd>
                      </div>
                      <div>
                        <dt>Адрес</dt>
                        <dd>{e.egrul.address}</dd>
                      </div>
                    </dl>
                  ) : (
                    <span className="small muted">Источник не ответил</span>
                  )}
                </div>
                <div className="panel">
                  <b>ФНС</b>
                  {e.fns ? (
                    <dl className="dl stacked">
                      <div>
                        <dt>Налоговый режим</dt>
                        <dd>{e.fns.tax_regime}</dd>
                      </div>
                      <div>
                        <dt>Долг перед налоговой</dt>
                        <dd>{money(e.fns.tax_debt_rub)}</dd>
                      </div>
                      <div>
                        <dt>Индекс надёжности</dt>
                        <dd>{e.fns.reliability_score} / 100</dd>
                      </div>
                       <div>
                         <dt>Массовый адрес / директор</dt>
                         <dd>
                           {yesNo(e.fns.mass_address)} / {yesNo(e.fns.mass_director)}
                         </dd>
                       </div>
                       <div>
                         <dt>Последняя отчётность</dt>
                         <dd>{date(e.fns.last_reporting_date)}</dd>
                       </div>
                     </dl>

                  ) : (
                    <span className="small muted">Источник не ответил</span>
                  )}
                </div>
                <div className="panel">
                  <b>БКИ</b>
                  {e.bki ? (
                    <dl className="dl stacked">
                      <div>
                        <dt>Кредитный рейтинг</dt>
                        <dd>{e.bki.credit_score}</dd>
                      </div>
                      <div>
                        <dt>Действующих кредитов</dt>
                        <dd>{e.bki.active_obligations_count}</dd>
                      </div>
                      <div>
                        <dt>Остаток долга</dt>
                        <dd>{money(e.bki.total_outstanding_rub)}</dd>
                      </div>
                       <div>
                         <dt>Текущая просрочка</dt>
                         <dd>{yesNo(e.bki.has_current_past_due)}</dd>
                       </div>
                       <div>
                         <dt>Обновлено в источнике</dt>
                         <dd>{date(e.bki.last_update)}</dd>
                       </div>
                     </dl>

                  ) : (
                    <span className="small muted">Источник не ответил</span>
                  )}
                </div>
              </div>
              <span className="xs muted">Снимок ответов мок-сервисов на момент подачи: {dateTime(a.created_at)}</span>
            </section>
          )}
        </div>

        <aside className="side stack">
          <section className="card tight">
            <h2 className="h3">Параметры заявки</h2>
            <dl className="dl">
              <div>
                <dt>Продукт</dt>
                <dd>
                  {name}
                  {a.product_selected_by_system && !noProduct(a) && <span className="xs muted"> · подобран банком</span>}
                </dd>
              </div>
              <div>
                <dt>Сумма</dt>
                <dd>{money(p.requested_amount_rub)}</dd>
              </div>
              <div>
                <dt>Срок</dt>
                <dd>{months(p.term_months)}</dd>
              </div>
              <div>
                <dt>Цель</dt>
                <dd>{PURPOSE_NAME[p.purpose]}</dd>
              </div>
              <div>
                <dt>Сегмент</dt>
                <dd>{SEGMENT_NAME[p.segment]}</dd>
              </div>
            </dl>
            <span className="xs muted">Сегмент определяет банк по числу сотрудников и выручке</span>
          </section>
          <section className="card tight">
            <h2 className="h3">Компания на момент подачи</h2>
            <dl className="dl">
              <div>
                <dt>Название</dt>
                <dd>{a.company.legal_name}</dd>
              </div>
              <div>
                <dt>ИНН · форма</dt>
                <dd>
                  {a.company.inn} · {LEGAL_FORM_NAME[a.company.legal_form]}
                </dd>
              </div>
              <div>
                <dt>ОКВЭД · регион</dt>
                <dd>
                  {a.company.okved} · {a.company.region}
                </dd>
              </div>
              <div>
                <dt>Зарегистрирована</dt>
                <dd>{date(a.company.registration_date)}</dd>
              </div>
              <div className="sep">
                <dt>Выручка за год</dt>
                <dd>{money(a.financials.annual_revenue_rub)}</dd>
              </div>
              <div>
                <dt>Чистая прибыль</dt>
                <dd>{money(a.financials.annual_net_profit_rub)}</dd>
              </div>
              <div>
                <dt>Платежи по кредитам в месяц</dt>
                <dd>{money(a.credit_history.monthly_debt_payments_rub)}</dd>
              </div>
              {a.enriched_data?.bank_credits && (
                <div>
                  <dt>Из них кредиты нашего банка</dt>
                  <dd>
                    {money(a.enriched_data.bank_credits.monthly_payments_rub)} · {a.enriched_data.bank_credits.count} шт.
                  </dd>
                </div>
              )}
              <div>
                <dt>Просрочка сейчас</dt>
                <dd>{yesNo(a.credit_history.has_current_past_due)}</dd>
              </div>
            </dl>
            {a.enriched_data?.bank_credits ? (
              <span className="xs muted">Кредитная история — из БКИ и кредиты, которые наш банк уже выдал, на момент подачи</span>
            ) : (
              a.enriched_data?.bki && <span className="xs muted">Кредитная история — из БКИ на момент подачи</span>
            )}
          </section>
          <section className="card tight">
            <h2 className="h3">История заявки</h2>
            {events.length === 0 ? (
              <span className="small muted">Событий пока нет</span>
            ) : (
              <ul className="feed">
                {events.map((ev) => (
                  <li key={ev.id}>
                    <span className="t">{time(ev.created_at)}</span>
                    <span className="dot" style={{ background: eventColor(ev) }} />
                    <span>{eventText(ev, bank)}</span>
                  </li>
                ))}
              </ul>
            )}
          </section>
          {a.consents && (
            <section className="card tight">
              <h2 className="h3">Согласия</h2>
              <dl className="dl">
                <div>
                  <dt>Персональные данные</dt>
                  <dd>{a.consents.personal_data_processing ? 'предоставлено' : 'нет'}</dd>
                </div>
                <div>
                  <dt>Кредитная история</dt>
                  <dd>{a.consents.credit_history_request ? 'предоставлено' : 'нет'}</dd>
                </div>
                <div>
                  <dt>Версия</dt>
                  <dd>{a.consents.version}</dd>
                </div>
                <div>
                  <dt>Принято</dt>
                  <dd>{dateTime(a.consents.accepted_at)}</dd>
                </div>
              </dl>
            </section>
          )}
        </aside>
      </div>
    </>
  );
}
