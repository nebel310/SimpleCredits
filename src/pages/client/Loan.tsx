import { Navigate, useParams } from 'react-router-dom';
import { productByCode } from '../../api/catalog';
import { date, dateTime, money, time } from '../../lib/format';
import { PRODUCT_NAME } from '../../lib/status';
import { AiHint, Chip, ErrorState, Loading, PageTitle, StatusBanner } from '../../ui/kit';
import { Px } from '../../ui/Px';
import { useAiScreen } from '../../ai/AiAssistant';
import { useApp } from './Applications';

export function Loan() {
  const { id } = useParams();
  const q = useApp(id);
  const app = q.data;
  useAiScreen('Кредит', { appId: id, chips: ['Что такое переплата?', 'Как устроен платёж?'] });

  if (q.error) return <ErrorState error={q.error} onRetry={() => q.reload()} />;
  if (!app) return <Loading lines={6} />;
  if (!['DISBURSEMENT', 'ACTIVE', 'REPAID'].includes(app.status)) return <Navigate to={`/applications/${app.id}`} replace />;
  const o = app.offer!;
  const p = productByCode(o.product);

  if (app.status === 'DISBURSEMENT') {
    const checking = app.disbursement?.status === 'checking';
    return (
      <>
        <PageTitle crumbs={`Заявки › № ${app.number}`} title={`${PRODUCT_NAME[o.product]} · ${money(o.amount)}`} />
        <StatusBanner
          kind="wait"
          icon="wait"
          chip={<Chip kind="mid">{checking ? 'Проверяем операцию' : 'Готовим перечисление'}</Chip>}
          title={checking ? 'Проверяем результат перечисления' : 'Договор подписан. Готовим перечисление'}
          facts={[
            { label: 'Договор подписан', value: dateTime(app.signing?.signedAt) },
            { label: 'Операция', value: app.disbursement?.operationId ?? '—' },
            { label: 'Что нужно от вас', value: 'Ничего — статус обновится здесь' },
          ]}
        >
          {checking ? (
            <span className="small">Банк не получил подтверждения от системы выдачи и сверяет статус операции. Повторно деньги не отправит — дождитесь подтверждения.</span>
          ) : (
            <span className="small">
              <span className="spin" style={{ width: 14, height: 14, marginRight: 8 }} />
              Деньги будут считаться зачисленными только после подтверждения банка.
            </span>
          )}
        </StatusBanner>
        <Events app={app} />
      </>
    );
  }

  const l = app.loan!;
  const paid = l.schedule.filter((x) => x.status === 'paid').length;
  const next = l.schedule.find((x) => x.status !== 'paid');
  return (
    <>
      <PageTitle crumbs={`Заявки › № ${app.number}`} title={`${PRODUCT_NAME[o.product]} · ${money(o.amount)}`} />
      <section className="hero dark">
        <div style={{ flex: '1 1 560px', minWidth: 0 }}>
          <Chip kind="lime">{app.status === 'REPAID' ? 'Погашен' : p.kind === 'limit' ? 'Лимит открыт' : 'Деньги на счёте'}</Chip>
          <h2 style={{ fontSize: 30, marginTop: 12 }}>{app.status === 'REPAID' ? 'Кредит полностью погашен' : p.kind === 'limit' ? `Лимит ${money(l.amount)} открыт на вашем счёте` : `${money(l.amount)} зачислены на ваш счёт`}</h2>
          <div className="small" style={{ marginTop: 10, color: 'rgba(255,255,255,.72)' }}>
            {dateTime(app.disbursement?.doneAt)} · счёт {l.account} · договор № КД-{app.number}
          </div>
          {p.kind === 'loan' && (
            <div style={{ display: 'grid', gridTemplateColumns: `repeat(${l.schedule.length}, 1fr)`, gap: 3, marginTop: 20 }} aria-label={`Выплачено ${paid} из ${l.schedule.length}`}>
              {l.schedule.map((x) => (
                <span key={x.n} style={{ height: 10, background: x.status === 'paid' ? 'var(--c-lime)' : x.status === 'overdue' ? 'var(--c-negative)' : '#3f3f45' }} />
              ))}
            </div>
          )}
        </div>
        <Px name="heart" size={84} color="var(--c-lime)" />
      </section>

      <div className="row">
        <div className="grow stack">
          {p.kind === 'loan' && next ? (
            <section className="card">
              <div className="row-c between">
                <div>
                  <div className="small muted">Дата следующего платежа</div>
                  <div className="display" style={{ fontSize: 40 }}>
                    {money(next.amount)}
                  </div>
                  <div className="small">
                    до {date(next.date)} · платёж № {next.n} из {l.schedule.length}
                  </div>
                </div>
                <Chip kind="mid">Запланирован</Chip>
              </div>
              <span className="xs muted">Держите сумму на счёте к дате платежа. Статус оплаты появится в ленте событий.</span>
            </section>
          ) : (
            <section className="card">
              <div className="grid-fields">
                <div>
                  <div className="small muted">Доступно</div>
                  <div className="h2">{money(l.amount - l.used)}</div>
                </div>
                <div>
                  <div className="small muted">Использовано</div>
                  <div className="h2">{money(l.used)}</div>
                </div>
                <div>
                  <div className="small muted">Проценты к оплате</div>
                  <div className="h2">{money(0)}</div>
                </div>
              </div>
              <span className="xs muted">Проценты начисляются только за дни, когда вы используете деньги лимита. Ставка {o.ratePct}% годовых (модельная).</span>
            </section>
          )}
          {p.kind === 'loan' && (
            <section className="card">
              <div className="row-c between">
                <h2 className="h2">График платежей</h2>
                <span className="small muted">
                  Выплачено {paid} из {l.schedule.length} · остаток долга {money(l.balance)}
                </span>
              </div>
              <div className="tbl-wrap">
                <table className="tbl">
                  <thead>
                    <tr>
                      <th>№</th>
                      <th>Дата</th>
                      <th>Платёж</th>
                      <th>Долг</th>
                      <th>Проценты</th>
                      <th>Статус</th>
                    </tr>
                  </thead>
                  <tbody>
                    {l.schedule.slice(0, 6).map((x) => (
                      <tr key={x.n}>
                        <td>{x.n}</td>
                        <td>{date(x.date)}</td>
                        <td>{money(x.amount)}</td>
                        <td>{money(x.principal)}</td>
                        <td>{money(x.interest)}</td>
                        <td>
                          <Chip kind={x.status === 'paid' ? 'high' : x.status === 'overdue' ? 'low' : 'neutral'}>{x.status === 'paid' ? 'Оплачен' : x.status === 'overdue' ? 'Просрочен' : 'Запланирован'}</Chip>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {l.schedule.length > 6 && <span className="xs muted">… ещё {l.schedule.length - 6} платежей</span>}
            </section>
          )}
        </div>
        <aside className="side stack">
          <Events app={app} />
          <AiHint>Если платёж не получается внести вовремя, лучше заранее написать в банк через кабинет — так проще договориться. Просрочки ухудшают кредитную историю.</AiHint>
        </aside>
      </div>
    </>
  );
}

function Events({ app }: { app: NonNullable<ReturnType<typeof useApp>['data']> }) {
  return (
    <section className="card tight">
      <h2 className="h3">Лента событий</h2>
      <ul className="feed">
        {app.events.slice(0, 8).map((e) => (
          <li key={e.id}>
            <span className="t">{time(e.at)}</span>
            <span className="dot" style={{ background: e.actor === 'client' ? 'var(--c-black)' : e.actor === 'bank' ? 'var(--c-red)' : e.actor === 'source' ? 'var(--c-mid)' : 'var(--c-high)' }} />
            <span>
              {e.client}
              <span className="who-s" style={{ display: 'block' }}>
                {dateTime(e.at)}
              </span>
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}
