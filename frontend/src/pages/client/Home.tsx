import { Link } from 'react-router-dom';
import { api, profileComplete, useSession } from '../../api';
import { useLiveUpdates } from '../../api/ws';
import { useQuery } from '../../lib/hooks';
import { loadProducts, productName } from '../../lib/catalog';
import { dateTime, short, money } from '../../lib/format';
import { LEGAL_FORM_NAME, appTitle, display } from '../../lib/labels';
import { Btn, Chip, EmptyState, ErrorState, Loading, PageTitle, StatusBanner } from '../../ui/kit';
import { Px } from '../../ui/Px';

const HOW = [
  ['Профиль компании', 'Реквизиты и финансы — один раз'],
  ['Заявка', 'Сумма, срок, цель и, если хотите, продукт'],
  ['Проверка', 'Банк запрашивает ЕГРЮЛ, ФНС и БКИ и оценивает риск'],
  ['Решение и оформление', 'Принимаете предложение — и кредит оформлен'],
];

export function Home() {
  const user = useSession((s) => s.user)!;
  const ready = profileComplete(user);
  const apps = useQuery(() => api.allApplications(), []);
  const products = useQuery(loadProducts, []);
  useLiveUpdates((m) => {
    if (m.type === 'reconnected' || m.type === 'status_changed') apps.reload(true);
  });
  const c = user.company;
  const f = user.financials;

  return (
    <>
      <PageTitle crumbs="Главная" title={c ? c.legal_name : `Здравствуйте, ${user.username}`} />
      {!ready ? (
        <StatusBanner
          kind="action"
          icon="doc"
          title="Заполните профиль компании"
          actions={
            <Btn view="accent" to="/profile">
              Заполнить профиль
            </Btn>
          }
        >
          Реквизиты и финансы нужны один раз — дальше они подставляются во все заявки. Реквизиты подтянем из ЕГРЮЛ по ИНН, кредитную историю банк возьмёт из БКИ.
        </StatusBanner>
      ) : (
        <section className="hero">
          <div style={{ flex: '1 1 560px', minWidth: 0 }}>
            <h2 style={{ fontSize: 30 }}>Нужны деньги на бизнес?</h2>
            <p>Подайте заявку — проверим данные компании и сразу покажем решение. Профиль уже заполнен.</p>
            <div className="btn-row" style={{ marginTop: 20 }}>
              <Btn view="primary" to="/apply">
                Новая заявка
              </Btn>
              <Link to="/products" style={{ color: '#fff' }}>
                Каталог продуктов
              </Link>
            </div>
          </div>
          <Px name="heart" size={98} color="var(--c-lime)" />
        </section>
      )}

      <div className="row">
        <section className="card grow">
          <div className="row-c between">
            <h2 className="h2">Последние заявки</h2>
            <Link to="/applications" className="small">
              Все заявки
            </Link>
          </div>
          {apps.error && <ErrorState error={apps.error} onRetry={() => apps.reload()} />}
          {!apps.data && !apps.error && <Loading lines={3} />}
          {apps.data && apps.data.length === 0 && <EmptyState title="Заявок пока нет" text={ready ? 'Подайте первую — решение придёт сразу' : 'Сначала заполните профиль компании'} />}
          {apps.data &&
            apps.data.slice(0, 3).map((a) => {
              const name = productName(products.data, a.application.product_type);
              const d = display(a, name);
              return (
                <Link key={a.application_id} to={`/applications/${a.application_id}`} className="panel row-panel" style={{ textDecoration: 'none', color: 'inherit' }}>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <b>{appTitle(a, name)}</b>
                    <div className="small muted">
                      {money(a.application.requested_amount_rub)} · подана {dateTime(a.created_at)}
                    </div>
                    {a.actions?.length && d.next ? <div className="xs" style={{ marginTop: 4, fontWeight: 600 }}>{d.next}</div> : null}
                  </div>
                  <Chip kind={d.kind}>{d.chip}</Chip>
                </Link>
              );
            })}
        </section>

        <aside className="side stack">
          {c && f && (
            <section className="card tight">
              <div className="row-c between">
                <h2 className="h3">Профиль компании</h2>
                <Link to="/profile" className="small">
                  Изменить
                </Link>
              </div>
              <dl className="dl">
                <div>
                  <dt>ИНН · форма</dt>
                  <dd>
                    {c.inn} · {LEGAL_FORM_NAME[c.legal_form]}
                  </dd>
                </div>
                <div>
                  <dt>Регион</dt>
                  <dd>{c.region}</dd>
                </div>
                <div>
                  <dt>Выручка за год</dt>
                  <dd>{short(f.annual_revenue_rub)}</dd>
                </div>
              </dl>
            </section>
          )}
          <section className="card tight">
            <h2 className="h3">Как это работает</h2>
            <ol className="how">
              {HOW.map(([t, d]) => (
                <li key={t}>
                  <b>{t}</b>
                  <span className="small muted">{d}</span>
                </li>
              ))}
            </ol>
          </section>
        </aside>
      </div>
    </>
  );
}
