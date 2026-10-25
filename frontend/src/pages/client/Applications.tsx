import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api } from '../../api';
import { useLiveUpdates } from '../../api/ws';
import { useQuery } from '../../lib/hooks';
import { loadProducts, productName } from '../../lib/catalog';
import { dateTime, money, months, rate } from '../../lib/format';
import { PURPOSE_NAME, appTitle, display } from '../../lib/labels';
import { Btn, Chip, EmptyState, ErrorState, Loading, PageTitle } from '../../ui/kit';
import { ApplicationView } from '../shared/ApplicationView';

export function ApplicationsList() {
  const products = useQuery(loadProducts, []);
  const all = useQuery(() => api.allApplications(), []);
  const [shown, setShown] = useState(20);

  // Новый статус по WebSocket — перечитываем список
  useLiveUpdates((m) => {
    if (m.type === 'reconnected' || m.type === 'status_changed') all.reload(true);
  });

  const items = (all.data ?? []).slice(0, shown);

  return (
    <>
      <PageTitle
        crumbs="Заявки"
        title="Мои заявки"
        right={
          <Btn view="accent" to="/apply">
            Новая заявка
          </Btn>
        }
      />
      {all.error && <ErrorState error={all.error} onRetry={() => all.reload()} />}
      {!all.data && !all.error && <Loading lines={5} />}
      {all.data && items.length === 0 && (
        <section className="card">
          <EmptyState
            title="Заявок пока нет"
            text="Подайте первую — решение придёт сразу после проверки"
            action={
              <Btn view="accent" to="/apply">
                Подать заявку
              </Btn>
            }
          />
        </section>
      )}
      {items.length > 0 && (
        <section className="card">
          <div className="tbl-wrap">
            <table className="tbl">
              <thead>
                <tr>
                  <th>Подана</th>
                  <th>Продукт</th>
                  <th>Сумма и срок</th>
                  <th>Цель</th>
                  <th>Предложение</th>
                  <th>Статус</th>
                </tr>
              </thead>
              <tbody>
                {items.map((a) => {
                  const name = productName(products.data, a.application.product_type);
                  const d = display(a, name);
                  return (
                  <tr key={a.application_id}>
                    <td className="nowrap">{dateTime(a.created_at)}</td>
                    <td>
                      <Link to={`/applications/${a.application_id}`}>{appTitle(a, name)}</Link>
                      {a.product_selected_by_system && <div className="xs muted">подобран банком</div>}
                    </td>
                    <td className="nowrap">
                      {money(a.application.requested_amount_rub)} · {months(a.application.term_months)}
                    </td>
                    <td>{PURPOSE_NAME[a.application.purpose]}</td>
                    <td className="nowrap">{a.offer ? `${money(a.offer.amount_rub)} · ${rate(a.offer.rate_percent)}` : '—'}</td>
                    <td>
                      <Chip kind={d.kind}>{d.chip}</Chip>
                    </td>
                  </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {(all.data?.length ?? 0) > shown && (
            <div>
              <Btn view="outlined" size={40} onClick={() => setShown((n) => n + 20)}>
                Показать ещё
              </Btn>
            </div>
          )}
        </section>
      )}
    </>
  );
}

export function ApplicationCard() {
  const { id } = useParams();
  return <ApplicationView id={id!} />;
}
