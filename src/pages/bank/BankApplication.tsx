import { useState } from 'react';
import { useParams } from 'react-router-dom';
import { api, CHECK_SOURCES, type ApplicationView } from '../../api';
import { REASON_CATALOG } from '../../api/catalog';
import { useAction, useQuery, useSession } from '../../lib/hooks';
import { ago, date, dateTime, dec2, money, pct, time } from '../../lib/format';
import { BANK_STATUS, PRODUCT_NAME } from '../../lib/status';
import { Btn, Chip, EmptyState, ErrorState, Loading, PageTitle, toast } from '../../ui/kit';
import { Px } from '../../ui/Px';
import { useAiScreen } from '../../ai/AiAssistant';
import { COMPANY_SHORT } from '../../lib/companies';

const SRC: Record<string, string> = { egrul: 'ФНС · ЕГРЮЛ', fns_tax: 'ФНС · налоги', bki: 'БКИ', fssp: 'ФССП', arbitr: 'Арбитраж', compliance: 'Комплаенс' };

export function useBankApp(id?: string) {
  const { session } = useSession();
  return useQuery(() => api.getApplication(session!, id!), [id, session?.userId]);
}

export function BankApplication() {
  const { id } = useParams();
  const { session, user } = useSession();
  const q = useBankApp(id);
  const [tab, setTab] = useState<'overview' | 'checks' | 'scoring' | 'docs' | 'journal'>('overview');
  const company = useQuery(() => (q.data ? api.getCompany(session!, q.data.companyId) : Promise.resolve(undefined)), [q.data?.companyId], { live: false });
  const take = useAction(async (key) => {
    await api.takeTask(session!, id!, key);
    toast('Заявка у вас в работе — действие записано в журнал');
  });
  const rerun = useAction(async () => {
    await api.rerunChecks(session!, id!);
    toast('Повторили запросы к источникам');
  });
  useAiScreen('Банк: карточка заявки', { appId: id, chips: ['Что такое DSCR?', 'Что такое комплаенс?', 'Почему отказ?'] });

  if (q.error) return <ErrorState error={q.error} onRetry={() => q.reload()} />;
  const app = q.data;
  if (!app) return <Loading lines={6} />;
  const c = company.data;
  const waiting = CHECK_SOURCES.filter((s) => app.checks[s]?.status === 'waiting');
  const missing = CHECK_SOURCES.filter((s) => !['ok', 'warning'].includes(app.checks[s]?.status ?? ''));
  const complianceOpen = !!app.checks.compliance?.match && !app.complianceResolved;
  const sc = app.scoring;
  const decideReason = app.permissions.decide ? null : user!.role !== 'underwriter' ? 'Решение принимает андеррайтер' : complianceOpen ? 'Ждём решения комплаенса' : missing.length && app.status !== 'DRAFT' ? 'Нет данных источников — финальное решение недоступно' : app.status !== 'MANUAL_REVIEW' ? 'Заявка не на этапе решения' : 'Решение по этому раунду уже принято';
  const mustTake = app.permissions.takeTask;

  return (
    <>
      <PageTitle
        crumbs={<span>Очередь задач › {app.number}</span>}
        title={`Заявка ${app.number} · ${COMPANY_SHORT[app.companyId]}`}
        right={
          <div className="btn-row">
            {mustTake && (
              <Btn view="primary" onClick={() => take.run()} loading={take.pending}>
                Взять в работу
              </Btn>
            )}
            {waiting.length > 0 && app.permissions.requestDocs !== undefined && (user!.role === 'manager' || user!.role === 'underwriter') && (
              <Btn view="outlined" onClick={() => rerun.run()} loading={rerun.pending}>
                Повторить запросы
              </Btn>
            )}
            {user!.role === 'underwriter' && (
              <Btn view="accent" to={`/bank/applications/${app.id}/decision`} disabled={!!decideReason || app.assignee?.userId !== user!.id} title={decideReason ?? (app.assignee?.userId !== user!.id ? 'Сначала возьмите заявку в работу' : undefined)}>
                Вынести решение
              </Btn>
            )}
          </div>
        }
      />
      <div className="row-c">
        <Chip kind="dark">{BANK_STATUS[app.status]}</Chip>
        <Chip kind="neutral">
          {PRODUCT_NAME[app.product]} · {money(app.amount)} · {app.termMonths} мес
        </Chip>
        <Chip kind="neutral">Раунд рассмотрения {app.round}</Chip>
        {app.assignee ? <Chip kind="mid">В работе: {app.assignee.name}</Chip> : <Chip kind="attention">Не назначена</Chip>}
        <span className="xs muted">в статусе {ago(app.statusSince)}</span>
        {app.committee && <Chip kind="attention">Кредитный комитет</Chip>}
      </div>
      {user!.role === 'underwriter' && decideReason && app.status === 'MANUAL_REVIEW' && <span className="xs muted">{decideReason}</span>}
      {take.error && <ErrorState error={take.error} />}

      <div className="seg" role="tablist" aria-label="Разделы заявки">
        {(
          [
            ['overview', 'Обзор'],
            ['checks', `Проверки · ${CHECK_SOURCES.length}`],
            ['scoring', 'Скоринг'],
            ['journal', 'Журнал'],
          ] as const
        ).map(([k, l]) => (
          <button key={k} type="button" role="tab" aria-selected={tab === k} aria-pressed={tab === k} onClick={() => setTab(k)}>
            {l}
          </button>
        ))}
      </div>

      {tab === 'overview' && (
        <div className="row">
          <div className="grow stack">
            <div className="grid-2">
              <section className="card tight">
                <span className="caps muted">Кредитный исход</span>
                {app.decision && app.decision.round === app.round ? (
                  <>
                    <b className="h3">{app.decision.outcome}</b>
                    <span className="small">
                      {app.decision.byName} · {dateTime(app.decision.at)}
                    </span>
                    {app.decision.reasons.map((r) => (
                      <span key={r.code} className="xs muted">
                        {r.bank}
                      </span>
                    ))}
                  </>
                ) : sc ? (
                  <>
                    <b className="h3">Рекомендация: {sc.recommendation.outcome}</b>
                    <span className="small muted">Рекомендация правил — не окончательное решение</span>
                  </>
                ) : (
                  <span className="small muted">Оценки ещё нет</span>
                )}
              </section>
              <section className="card tight">
                <span className="caps muted">Техническое состояние</span>
                {waiting.length ? (
                  <>
                    <b className="h3" style={{ color: 'var(--c-mid-ink)' }}>Ждём источники: {waiting.map((w) => SRC[w]).join(', ')}</b>
                    <span className="small muted">Повтор запроса автоматический. Это не влияет на кредитный исход.</span>
                  </>
                ) : missing.length ? (
                  <>
                    <b className="h3">Проверки идут</b>
                    <span className="small muted">Ответили {CHECK_SOURCES.length - missing.length} из {CHECK_SOURCES.length}</span>
                  </>
                ) : (
                  <>
                    <b className="h3" style={{ color: 'var(--c-positive)' }}>Все источники ответили</b>
                    <span className="small muted">Последний ответ {dateTime(CHECK_SOURCES.map((s) => app.checks[s]?.answeredAt ?? '').sort().pop())}</span>
                  </>
                )}
              </section>
            </div>
            {missing.length > 0 && ['MANUAL_REVIEW', 'WAITING_SOURCE', 'CHECKS'].includes(app.status) && (
              <div className="warn-box">
                Нет данных: {missing.map((m) => SRC[m]).join(', ')}. Финальное решение недоступно, пока данные не придут. Можно повторить запрос или запросить у клиента документы.
              </div>
            )}
            {app.needsRescore && <div className="info-box">Документ принят — нужна повторная оценка. Система пересчитывает скоринг.</div>}
            {sc && (
              <section className="card">
                <div className="row-c between">
                  <h2 className="h2">Что говорят правила</h2>
                  <span className="xs muted">
                    правила {sc.rulesVersion} · {dateTime(sc.at)}
                  </span>
                </div>
                <div className="grid-3" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(min(200px, 100%), 1fr))', gap: 12 }}>
                  <div className="panel">
                    <span className="caps muted">1 · Стоп-факторы</span>
                    {sc.hardStops.some((h) => h.triggered) ? (
                      <b style={{ color: 'var(--c-negative-ink)' }}>
                        Сработали: {sc.hardStops.filter((h) => h.triggered).map((h) => h.code).join(', ')}
                      </b>
                    ) : (
                      <b className="row-c" style={{ gap: 8 }}>
                        <span style={{ width: 10, height: 10, background: 'var(--c-high)' }} /> Не сработали
                      </b>
                    )}
                    <span className="xs muted">{sc.hardStops.length} правил проверено</span>
                  </div>
                  <div className="panel">
                    <span className="caps muted">2 · Скоринг</span>
                    <div className="row-c" style={{ alignItems: 'baseline' }}>
                      <span className="num" style={{ fontSize: 28 }}>
                        {sc.score}
                      </span>
                      <span className="muted">из 100</span>
                      <Chip kind={sc.category <= 'B' ? 'high' : sc.category === 'C' ? 'mid' : 'low'}>Категория {sc.category}</Chip>
                    </div>
                  </div>
                  <div className="panel">
                    <span className="caps muted">3 · Платёжеспособность</span>
                    <b>
                      DSCR при {money(app.amount)}: <span style={{ color: sc.dscr < 1.3 ? 'var(--c-negative-ink)' : 'var(--c-positive)' }}>{dec2(sc.dscr)}</span>
                    </b>
                    <span className="xs muted">минимум 1,3 · нагрузка {pct(sc.debtLoadPct)}</span>
                  </div>
                </div>
                <div className="panel row-panel" style={{ background: 'var(--c-black)', color: '#fff' }}>
                  <div style={{ flex: '1 1 320px' }}>
                    <span className="xs" style={{ color: '#babbc2' }}>
                      Рекомендация правил
                    </span>
                    <div style={{ fontWeight: 700 }}>
                      {sc.recommendation.outcome}
                      {sc.recommendation.amount ? `: ${money(sc.recommendation.amount)} на ${sc.recommendation.termMonths} мес · DSCR ${dec2(sc.recommendation.dscrAtAmount ?? 0)}` : ''}
                    </div>
                    <span className="xs" style={{ color: '#babbc2' }}>
                      {sc.recommendation.reasonCodes.map((r) => REASON_CATALOG[r]?.bank ?? r).join(' · ')}
                    </span>
                  </div>
                </div>
              </section>
            )}
          </div>
          <aside className="side stack">
            <section className="card tight">
              <h2 className="h3">Компания</h2>
              {c && (
                <dl className="stack-s" style={{ margin: 0, fontSize: 14 }}>
                  <div>
                    <dt className="xs muted">ИНН · {c.type === 'IP' ? 'ОГРНИП' : 'ОГРН'}</dt>
                    <dd style={{ margin: 0, fontWeight: 600 }}>
                      {c.inn} · {c.ogrn}
                    </dd>
                  </div>
                  <div>
                    <dt className="xs muted">Регистрация · ОКВЭД</dt>
                    <dd style={{ margin: 0, fontWeight: 600 }}>
                      {date(c.regDate)} · {c.okved}
                    </dd>
                  </div>
                  <div>
                    <dt className="xs muted">Руководитель</dt>
                    <dd style={{ margin: 0, fontWeight: 600 }}>
                      {c.head} · паспорт {app.sensitive?.headPassport}
                    </dd>
                  </div>
                  <div>
                    <dt className="xs muted">Подтверждение компании</dt>
                    <dd style={{ margin: 0, fontWeight: 600 }}>{app.companyConfirmed === 'manual' ? `Вручную: ${app.manualCompanyNote}` : 'По реестру'}</dd>
                  </div>
                </dl>
              )}
              <span className="xs muted">Персональные данные скрыты по ролям: полностью видят андеррайтер и комплаенс.</span>
            </section>
            <section className="card tight">
              <h2 className="h3">Финансы</h2>
              <dl className="dl" style={{ fontSize: 14 }}>
                <div>
                  <dt>Выручка за год</dt>
                  <dd>{money(app.finance.revenueYear.value)}</dd>
                </div>
                <div>
                  <dt>Поступления у нас</dt>
                  <dd>{money(app.finance.inflows3m.value)}/мес</dd>
                </div>
                {sc && (
                  <div>
                    <dt>Денежный поток</dt>
                    <dd>{money(sc.cashFlow)}/мес</dd>
                  </div>
                )}
                <div>
                  <dt>Текущие платежи</dt>
                  <dd>{app.finance.hasLoans ? money(app.finance.loanPayments) : 'нет'}</dd>
                </div>
                <div>
                  <dt>Поручитель</dt>
                  <dd>{app.finance.guarantor === 'none' ? 'нет' : app.finance.guarantor === 'owner' ? 'владелец' : app.finance.guarantorName}</dd>
                </div>
              </dl>
              {app.finance.comment && <div className="info-box">Комментарий клиента: «{app.finance.comment}»</div>}
              {app.documents.filter((d) => d.status === 'accepted').map((d) => (
                <div key={d.id} className="ai-hint" style={{ padding: 12 }}>
                  <span className="small">
                    <Px name="gem" size={12} color="var(--c-ai)" /> {d.title}: {d.fields.find((f) => f.key === 'avg')?.value}/мес — распознал ИИ, подтвердил клиент, принял менеджер
                  </span>
                </div>
              ))}
            </section>
            <section className="card tight">
              <h2 className="h3">Журнал</h2>
              <Journal app={app} limit={6} />
            </section>
          </aside>
        </div>
      )}

      {tab === 'checks' && (
        <section className="card">
          <div className="row-c between">
            <h2 className="h2">Внешние проверки</h2>
            {waiting.length > 0 && (user!.role === 'manager' || user!.role === 'underwriter') && (
              <Btn view="outlined" size={40} onClick={() => rerun.run()} loading={rerun.pending}>
                Повторить запросы
              </Btn>
            )}
          </div>
          <div className="tbl-wrap">
            <table className="tbl">
              <thead>
                <tr>
                  <th>Источник</th>
                  <th>Статус</th>
                  <th>Результат</th>
                  <th>Запрос</th>
                  <th>Ответ (актуальность)</th>
                  <th>Попыток</th>
                </tr>
              </thead>
              <tbody>
                {CHECK_SOURCES.map((s) => {
                  const ch = app.checks[s];
                  const st = ch?.status ?? 'pending';
                  return (
                    <tr key={s}>
                      <td>
                        <b>{SRC[s]}</b>
                      </td>
                      <td>
                        <Chip kind={st === 'ok' ? 'high' : st === 'warning' ? (ch?.match ? 'low' : 'attention') : st === 'waiting' ? 'mid' : 'neutral'}>{st === 'ok' ? 'SUCCESS' : st === 'warning' ? (ch?.match ? 'Совпадение' : 'Есть замечание') : st === 'waiting' ? 'TIMEOUT · повтор' : st === 'running' ? 'Запрос…' : 'В очереди'}</Chip>
                      </td>
                      <td className="small">{ch?.summary ?? '—'}</td>
                      <td className="small">{time(ch?.requestedAt)}</td>
                      <td className="small">{ch?.answeredAt ? `${dateTime(ch.answeredAt)}` : '—'}</td>
                      <td className="small">{ch?.attempts ?? 0}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <span className="xs muted">Техническая недоступность источника (TIMEOUT/ERROR) и реальный результат проверки (например, совпадение по комплаенсу) показываются отдельно.</span>
        </section>
      )}

      {tab === 'scoring' && (
        <section className="card">
          {!sc ? (
            <EmptyState title="Скоринга ещё нет" text="Он появится после проверок источников." />
          ) : (
            <>
              <div className="row-c between">
                <h2 className="h2">Скоринг: вклад факторов</h2>
                <span className="small muted">
                  {sc.rulesVersion} · {dateTime(sc.at)} · раунд {sc.round}
                </span>
              </div>
              <div className="tbl-wrap">
                <table className="tbl">
                  <thead>
                    <tr>
                      <th>Фактор</th>
                      <th>Значение (признак)</th>
                      <th style={{ width: 220 }}>Баллы</th>
                    </tr>
                  </thead>
                  <tbody>
                    {sc.factors.map((f) => (
                      <tr key={f.key}>
                        <td>
                          <b>{f.name}</b>
                        </td>
                        <td className="small">{f.value}</td>
                        <td>
                          <div className="row-c" style={{ flexWrap: 'nowrap' }}>
                            <div style={{ flex: 1, height: 10, background: 'var(--c-line)' }}>
                              <div style={{ width: `${(f.points / f.max) * 100}%`, height: '100%', background: f.points / f.max < 0.5 ? 'var(--c-negative)' : 'var(--c-black)' }} />
                            </div>
                            <b className="small nowrap">
                              {f.points}/{f.max}
                            </b>
                          </div>
                        </td>
                      </tr>
                    ))}
                    <tr>
                      <td>
                        <b>Итого</b>
                      </td>
                      <td className="small">Категория {sc.category}: A ≥ 80 · B ≥ 70 · C ≥ 50 · D ≥ 35</td>
                      <td>
                        <b>{sc.score}/100</b>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <h3 className="h3">Стоп-факторы</h3>
              <ul style={{ margin: 0, padding: 0, listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 6 }}>
                {sc.hardStops.map((h) => (
                  <li key={h.code} className="row-c small">
                    <Chip kind={h.triggered ? 'low' : 'high'}>{h.triggered ? 'Сработал' : 'Нет'}</Chip> {h.code} — {h.text}
                  </li>
                ))}
              </ul>
              <h3 className="h3">История перерасчётов</h3>
              <ul style={{ margin: 0, padding: 0, listStyle: 'none' }} className="small">
                {app.scoringHistory.map((h) => (
                  <li key={h.id} style={{ padding: '6px 0', borderTop: '1px solid var(--c-line)' }}>
                    {dateTime(h.at)} · раунд {h.round} · {h.score}/100, категория {h.category} · {h.trigger}
                  </li>
                ))}
              </ul>
            </>
          )}
        </section>
      )}

      {tab === 'journal' && (
        <section className="card">
          <h2 className="h2">Журнал</h2>
          <span className="small muted">Все действия людей, системы и источников. Изменения данных фиксируются.</span>
          <Journal app={app} />
        </section>
      )}
    </>
  );
}

export function Journal({ app, limit }: { app: ApplicationView; limit?: number }) {
  const items = limit ? app.events.slice(0, limit) : app.events;
  return (
    <ul className="feed">
      {items.map((e) => (
        <li key={e.id}>
          <span className="t">{time(e.at)}</span>
          <span className="dot" style={{ background: e.actor === 'client' ? 'var(--c-black)' : e.actor === 'bank' ? 'var(--c-red)' : e.actor === 'source' ? 'var(--c-mid)' : e.actor === 'ai' ? 'var(--c-ai)' : 'var(--c-high)' }} />
          <span>
            <b>{e.actorName}:</b> {e.bank}
            {!e.client && <span className="who-s"> · видит только банк</span>}
          </span>
        </li>
      ))}
    </ul>
  );
}
