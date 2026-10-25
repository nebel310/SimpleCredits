import { useEffect } from 'react';
import { api, type Application, type AppEvent, type Product } from '../../api';
import { useLiveUpdates } from '../../api/ws';
import { useAction, useQuery } from '../../lib/hooks';
import { loadProducts, productByType, productName } from '../../lib/catalog';
import { date, dateTime, money, months, pct, time } from '../../lib/format';
import { CONDITION_NAME, DECISION_NAME, FEATURE_NOT_IN_APPLICATION, factorAdvice, factorTitle, GRADE_KIND, LEGAL_FORM_NAME, POLICY_REASON, PURPOSE_NAME, SEGMENT_NAME, STATUS, eventText, outcomeText, trackIndex } from '../../lib/labels';
import { Btn, Chip, EmptyState, ErrorState, Loading, Meter, PageTitle, StatusBanner, Tracker } from '../../ui/kit';

const yesNo = (b: boolean) => (b ? 'да' : 'нет');

/** Карточка заявки: решение скоринга, факторы, данные госисточников, история. Общая для клиента и банка */
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
  // Запасной вариант, пока статус pending (и для банка, которому WebSocket не шлёт события)
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

  const actions = bank ? null : reduce ? (
    <>
      <Btn view="accent" to={`/apply?product=${code ?? ''}&amount=${reduce.recommended_amount_rub}&term=${p.term_months}&purpose=${p.purpose}`}>
        Подать заявку на {money(reduce.recommended_amount_rub)}
      </Btn>
      <Btn view="outlined" to="/applications">
        К списку заявок
      </Btn>
    </>
  ) : a.status === 'declined' || a.status === 'failed' ? (
    <Btn view="outlined" to="/apply">
      Новая заявка
    </Btn>
  ) : null;

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
      <Tracker index={trackIndex(a.status, events)} stop={a.status === 'declined' || a.status === 'failed'} />
      <StatusBanner
        kind={meta.banner}
        icon={meta.icon}
        chip={<Chip kind={meta.kind}>{meta.chip}</Chip>}
        title={out.title}
        actions={actions}
        facts={[
          { label: 'Сумма', value: money(p.requested_amount_rub) },
          reduce ? { label: 'Рекомендуемая сумма', value: money(reduce.recommended_amount_rub) } : { label: 'Срок', value: months(p.term_months) },
          { label: 'Цель', value: PURPOSE_NAME[p.purpose] },
        ]}
      >
        {out.text}
      </StatusBanner>

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
          {s ? (
            <section className="card">
              <div className="row-c between">
                <h2 className="h2">Решение скоринга</h2>
                <span className="xs muted">
                  Модель {s.model_version}
                  {s.scored_at ? ` · ${dateTime(s.scored_at)}` : ''}
                </span>
              </div>
              <div className="kpis">
                <div className="kpi">
                  <span className="muted small">Скоринговый балл</span>
                  <b className="num" style={{ fontSize: 36 }}>
                    {s.score}
                    <span className="muted" style={{ fontSize: 16 }}> / 1000</span>
                  </b>
                  <Meter value={s.score / 10} color="var(--c-black)" />
                </div>
                <div className="kpi">
                  <span className="muted small">Грейд риска</span>
                  <b className="num" style={{ fontSize: 36 }}>
                    {s.risk_grade}
                  </b>
                  <Chip kind={GRADE_KIND[s.risk_grade]}>{s.risk_grade <= 'B' ? 'низкий риск' : s.risk_grade === 'C' ? 'средний риск' : 'высокий риск'}</Chip>
                </div>
                <div className="kpi">
                  <span className="muted small">Вероятность дефолта</span>
                  <b className="num" style={{ fontSize: 36 }}>
                    {pct(s.pd * 100)}
                  </b>
                  <span className="xs muted">оценка модели, PD</span>
                </div>
              </div>
              {dec && (
                <dl className="dl">
                  <div>
                    <dt>Решение модели</dt>
                    <dd>{DECISION_NAME[dec.decision]}</dd>
                  </div>
                  {dec.reason_codes.map((r) => (
                    <div key={r}>
                      <dt>Причина</dt>
                      <dd>{POLICY_REASON[r] ?? r}</dd>
                    </div>
                  ))}
                  {cond.map((c) => (
                    <div key={c.code}>
                      <dt>Условие · {CONDITION_NAME[c.code] ?? c.code}</dt>
                      <dd>
                        {c.description}: {money(c.recommended_amount_rub)}
                      </dd>
                    </div>
                  ))}
                </dl>
              )}
            </section>
          ) : (
            a.status !== 'pending' && (
              <section className="card">
                <EmptyState title="Скоринга нет" text="Модель не вернула результат для этой заявки" />
              </section>
            )
          )}

          {s && s.reason_codes.length > 0 && (
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
                <dd>{name}</dd>
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
              <div>
                <dt>Просрочка сейчас</dt>
                <dd>{yesNo(a.credit_history.has_current_past_due)}</dd>
              </div>
            </dl>
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
                    <span className="dot" style={{ background: ev.event_type === 'failed' ? 'var(--c-negative)' : ev.event_type === 'status_changed' ? 'var(--c-red)' : 'var(--c-high)' }} />
                    <span>{eventText(ev)}</span>
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
