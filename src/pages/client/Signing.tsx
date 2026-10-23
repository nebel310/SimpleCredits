import { useEffect, useState } from 'react';
import { Navigate, useNavigate, useParams } from 'react-router-dom';
import { api } from '../../api';
import { productByCode } from '../../api/catalog';
import { useAction, useSession } from '../../lib/hooks';
import { date, dateTime, money } from '../../lib/format';
import { annuity } from '../../lib/calc';
import { PRODUCT_NAME } from '../../lib/status';
import { AiHint, Btn, Check, Chip, ErrorState, Loading, PageTitle, RoleGuard, StatusBanner } from '../../ui/kit';
import { useAiScreen } from '../../ai/AiAssistant';
import { useApp } from './Applications';

export function Signing() {
  const { id } = useParams();
  const { session, user } = useSession();
  const nav = useNavigate();
  const q = useApp(id);
  const app = q.data;
  const [read, setRead] = useState(false);
  const sign = useAction(async (key) => {
    await api.signContract(session!, id!, key);
  });
  useAiScreen('Подписание договора', { appId: id, chips: ['Что я подписываю?', 'Кто должен подписать?', 'Сколько я переплачу?'] });

  useEffect(() => {
    if (app?.status === 'DISBURSEMENT' || app?.status === 'ACTIVE') nav(`/applications/${app.id}/loan`, { replace: true });
  }, [app?.status, app?.id, nav]);

  if (q.error) return <ErrorState error={q.error} onRetry={() => q.reload()} />;
  if (!app) return <Loading lines={6} />;
  if (['DISBURSEMENT', 'ACTIVE', 'REPAID'].includes(app.status)) return <Navigate to={`/applications/${app.id}/loan`} replace />;
  if (app.status !== 'SIGNING' || !app.offer || !app.signing) return <Navigate to={`/applications/${app.id}`} replace />;

  const o = app.offer;
  const p = productByCode(o.product);
  const sg = app.signing;
  const expired = new Date(o.validUntil).getTime() < Date.now();
  const signing = sg.status === 'signing' || sign.pending;
  const docs = ['Кредитный договор', p.kind === 'loan' ? 'График платежей' : 'Условия лимита овердрафта', ...(app.finance.guarantor !== 'none' ? ['Договор поручительства'] : [])];
  const pay = p.kind === 'loan' ? annuity(o.amount, o.ratePct, o.termMonths) : 0;

  return (
    <>
      <PageTitle crumbs={`Заявки › № ${app.number} › Подписание`} title="Подписание договора" />
      <StatusBanner
        kind={sg.status === 'error' ? 'error' : 'action'}
        icon={sg.status === 'error' ? 'alert' : 'doc'}
        chip={<Chip kind={sg.status === 'error' ? 'low' : 'mid'}>{sg.status === 'error' ? 'Подпись не прошла' : signing ? 'Подписываем…' : 'Ожидает подписи'}</Chip>}
        title={o.kind === 'counter' ? `Вы приняли предложение банка: ${money(o.amount)}` : `Вы приняли условия: ${money(o.amount)}`}
        facts={[
          { label: 'Версия предложения', value: `${o.version}, принята ${dateTime(o.acceptedAt)}` },
          { label: 'Действует до', value: date(o.validUntil) },
          { label: 'Подписывает', value: 'Владелец (руководитель)' },
        ]}
      >
        {sg.status === 'error' && <span className="small">{sg.error}</span>}
      </StatusBanner>
      {expired && <ErrorState error="Срок действия предложения истёк — подписать нельзя. Подайте новую заявку." />}

      <div className="row">
        <div className="grow stack">
          <section className="card">
            <h2 className="h2">Условия</h2>
            <dl className="dl">
              <div>
                <dt>Продукт</dt>
                <dd>{PRODUCT_NAME[o.product]}</dd>
              </div>
              <div>
                <dt>{p.kind === 'limit' ? 'Лимит' : 'Сумма'}</dt>
                <dd>{money(o.amount)}</dd>
              </div>
              <div>
                <dt>Срок</dt>
                <dd>{o.termMonths} мес</dd>
              </div>
              <div>
                <dt>Ставка</dt>
                <dd>
                  {o.ratePct}% годовых{p.kind === 'limit' ? ' за дни использования' : ''}
                </dd>
              </div>
              {p.kind === 'loan' && (
                <div>
                  <dt>Платёж в месяц</dt>
                  <dd>{money(o.monthlyPayment)}</dd>
                </div>
              )}
              {o.fees.map((f) => (
                <div key={f.name}>
                  <dt>{f.name}</dt>
                  <dd>{money(f.amount)}</dd>
                </div>
              ))}
              <div>
                <dt>Обеспечение</dt>
                <dd>{o.collateral}</dd>
              </div>
              <div className="sep">
                <dt>{p.kind === 'limit' ? 'Стоимость при 50% использования' : 'Переплата за весь срок'}</dt>
                <dd>{money(o.overpayment)}</dd>
              </div>
            </dl>
          </section>
          {p.kind === 'loan' && (
            <section className="card">
              <h2 className="h2">График платежей</h2>
              <div className="tbl-wrap">
                <table className="tbl">
                  <thead>
                    <tr>
                      <th>№</th>
                      <th>Дата</th>
                      <th>Платёж</th>
                    </tr>
                  </thead>
                  <tbody>
                    {[1, 2, 3].map((n) => {
                      const dd = new Date();
                      dd.setMonth(dd.getMonth() + n);
                      return (
                        <tr key={n}>
                          <td>{n}</td>
                          <td>{date(dd.toISOString())}</td>
                          <td>{money(pay)}</td>
                        </tr>
                      );
                    })}
                    <tr>
                      <td colSpan={3} className="muted small">
                        … ещё {o.termMonths - 3} платежей. Даты точные после выдачи
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </section>
          )}
          <section className="card">
            <h2 className="h2">Подпись</h2>
            <RoleGuard allowed={app.permissions.sign} role={user!.role} what="Подписать договор">
              <Check checked={read} onChange={setRead} label="Я прочитал договор и график платежей" disabled={signing || expired} />
              <div className="btn-row">
                <Btn view="accent" onClick={() => sign.run()} loading={signing} disabled={!read || expired}>
                  {signing ? 'Подписываем…' : sg.status === 'error' ? 'Подписать ещё раз' : 'Подписать договор'}
                </Btn>
                <span className="xs muted">Подписание в кабинете, без SMS. Повторное нажатие не создаст второй подписи.</span>
              </div>
              {sign.error && <ErrorState error={sign.error} />}
            </RoleGuard>
          </section>
        </div>
        <aside className="side stack">
          <section className="card tight">
            <h2 className="h3">Документы</h2>
            {docs.map((d) => (
              <div key={d} className="row-c between small" style={{ flexWrap: 'nowrap' }}>
                <span>{d}</span>
                <span className="linkbtn" role="button" tabIndex={0}>
                  PDF
                </span>
              </div>
            ))}
          </section>
          <section className="card tight">
            <h2 className="h3">Участники</h2>
            {sg.participants.map((x) => (
              <div key={x.role} className="row-c between small" style={{ flexWrap: 'nowrap' }}>
                <span>
                  <b>{x.name}</b>
                  <span className="xs muted" style={{ display: 'block' }}>
                    {x.role}
                  </span>
                </span>
                <Chip kind={x.status === 'signed' ? 'high' : 'mid'}>{x.status === 'signed' ? 'Подписано' : 'Ждём подпись'}</Chip>
              </div>
            ))}
            {app.finance.guarantor === 'third_party' && <span className="xs muted">Поручитель получит задачу подписать договор поручительства в своём кабинете.</span>}
          </section>
          <AiHint>После подписи банк начнёт готовить перечисление. Деньги считаются зачисленными только после подтверждения банка — статус появится здесь.</AiHint>
        </aside>
      </div>
    </>
  );
}
