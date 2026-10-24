import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { api, type AppStatus, type ProductType, type RiskGrade } from '../../api';
import { useQuery } from '../../lib/hooks';
import { loadProducts, productName } from '../../lib/catalog';
import { dateTime, money, months } from '../../lib/format';
import { GRADE_KIND, STATUS } from '../../lib/labels';
import { Btn, Chip, EmptyState, ErrorState, Loading, PageTitle } from '../../ui/kit';
import { ApplicationView } from '../shared/ApplicationView';

// Кабинет банка — роль admin: GET /admin/applications, /admin/stats/overview, /scoring/model-info

const METRIC_NAME: Record<string, string> = {
  roc_auc_test: 'ROC-AUC (тест)',
  roc_auc_train: 'ROC-AUC (обучение)',
  gini_test: 'Gini (тест)',
  ks_test: 'KS (тест)',
  brier_test: 'Brier (тест)',
  pd_mean_test: 'Средний PD (тест)',
};

function Bars({ data, label, kind }: { data: Record<string, number>; label: (k: string) => string; kind?: (k: string) => string }) {
  const entries = Object.entries(data).sort((a, b) => b[1] - a[1]);
  const max = Math.max(1, ...entries.map(([, v]) => v));
  if (entries.length === 0) return <span className="small muted">Пока пусто</span>;
  return (
    <ul className="bars">
      {entries.map(([k, v]) => (
        <li key={k}>
          <span className="small">{label(k)}</span>
          <span className="bar" aria-hidden="true">
            <span style={{ width: `${(v / max) * 100}%`, background: kind?.(k) ?? 'var(--c-black)' }} />
          </span>
          <b className="small">{v}</b>
        </li>
      ))}
    </ul>
  );
}

const STATUS_COLOR: Record<AppStatus, string> = { confirmed: 'var(--c-high)', different: 'var(--c-attention)', declined: 'var(--c-negative)', failed: 'var(--c-negative-ink)', pending: 'var(--c-mid)' };

export function Admin() {
  const nav = useNavigate();
  const products = useQuery(loadProducts, []);
  const stats = useQuery(() => api.adminStats(), []);
  const model = useQuery(() => api.modelInfo(), []);
  const all = useQuery(() => api.allAdminApplications(), []);
  const [shown, setShown] = useState(20);
  const refresh = () => {
    stats.reload(true);
    all.reload(true);
  };
  // Банку WebSocket не шлёт события чужих заявок — обновляем раз в 15 секунд
  useEffect(() => {
    const t = setInterval(refresh, 15000);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const items = (all.data ?? []).slice(0, shown);
  const s = stats.data;
  const by = (st: AppStatus) => s?.by_status[st] ?? 0;

  return (
    <>
      <PageTitle
        crumbs="Кабинет банка"
        title="Заявки и статистика"
        right={
          <Btn view="outlined" size={40} onClick={refresh}>
            Обновить
          </Btn>
        }
      />
      {stats.error && <ErrorState error={stats.error} onRetry={() => stats.reload()} />}
      {s && (
        <div className="kpis">
          <div className="kpi card tight">
            <span className="small muted">Всего заявок</span>
            <b className="num" style={{ fontSize: 34 }}>
              {s.total}
            </b>
          </div>
          <div className="kpi card tight">
            <span className="small muted">Средний балл</span>
            <b className="num" style={{ fontSize: 34 }}>
              {s.avg_score === null ? '—' : Math.round(s.avg_score)}
            </b>
          </div>
          {(['confirmed', 'different', 'declined', 'failed'] as AppStatus[]).map((st) => (
            <div key={st} className="kpi card tight">
              <span className="small muted">{STATUS[st].chip}</span>
              <b className="num" style={{ fontSize: 34 }}>
                {by(st)}
              </b>
            </div>
          ))}
        </div>
      )}
      <div className="grid-3">
        <section className="card">
          <h2 className="h3">По статусам</h2>
          {s ? <Bars data={s.by_status} label={(k) => STATUS[k as AppStatus]?.chip ?? k} kind={(k) => STATUS_COLOR[k as AppStatus] ?? 'var(--c-black)'} /> : <Loading lines={2} />}
        </section>
        <section className="card">
          <h2 className="h3">По продуктам</h2>
          {s ? <Bars data={s.by_product_type} label={(k) => productName(products.data, k as ProductType)} /> : <Loading lines={2} />}
        </section>
        <section className="card">
          <h2 className="h3">По грейдам риска</h2>
          {s ? <Bars data={s.by_risk_grade} label={(k) => `Грейд ${k}`} kind={(k) => (GRADE_KIND[k as RiskGrade] === 'high' ? 'var(--c-high)' : GRADE_KIND[k as RiskGrade] === 'low' ? 'var(--c-negative)' : 'var(--c-attention)')} /> : <Loading lines={2} />}
        </section>
      </div>

      <section className="card">
        <div className="row-c between">
          <h2 className="h2">Все заявки</h2>
          <span className="small muted">Обновляется раз в 15 секунд</span>
        </div>
        {all.error && <ErrorState error={all.error} onRetry={() => all.reload()} />}
        {!all.data && !all.error && <Loading lines={4} />}
        {all.data && items.length === 0 && <EmptyState title="Заявок пока нет" text="Они появятся, когда клиенты начнут подавать заявки" />}
        {items.length > 0 && (
          <div className="tbl-wrap">
            <table className="tbl">
              <thead>
                <tr>
                  <th>Подана</th>
                  <th>Компания</th>
                  <th>Продукт</th>
                  <th>Сумма и срок</th>
                  <th>Балл · грейд</th>
                  <th>Статус</th>
                </tr>
              </thead>
              <tbody>
                {items.map((a) => (
                  <tr key={a.application_id} className="clickable" onClick={() => nav(`/bank/applications/${a.application_id}`)}>
                    <td className="nowrap">{dateTime(a.created_at)}</td>
                    <td>
                      <b>{a.company.legal_name}</b>
                      <div className="xs muted">ИНН {a.company.inn}</div>
                    </td>
                    <td>{productName(products.data, a.application.product_type)}</td>
                    <td className="nowrap">
                      {money(a.application.requested_amount_rub)} · {months(a.application.term_months)}
                    </td>
                    <td>
                      {a.scoring_result ? (
                        <>
                          {a.scoring_result.score} · <Chip kind={GRADE_KIND[a.scoring_result.risk_grade]}>{a.scoring_result.risk_grade}</Chip>
                        </>
                      ) : (
                        '—'
                      )}
                    </td>
                    <td>
                      <Chip kind={STATUS[a.status].kind}>{STATUS[a.status].chip}</Chip>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {(all.data?.length ?? 0) > shown && (
          <div>
            <Btn view="outlined" size={40} onClick={() => setShown((n) => n + 20)}>
              Показать ещё
            </Btn>
          </div>
        )}
      </section>

      <section className="card">
        <h2 className="h2">Скоринговая модель</h2>
        {model.error && <ErrorState error={model.error} onRetry={() => model.reload()} />}
        {model.data && (
          <>
            <dl className="dl-grid">
              <div>
                <dt>Версия</dt>
                <dd>{model.data.model_version}</dd>
              </div>
              <div>
                <dt>Тип</dt>
                <dd>{model.data.model_type}</dd>
              </div>
              <div>
                <dt>Обучена</dt>
                <dd>{model.data.trained_at ? dateTime(model.data.trained_at) : '—'}</dd>
              </div>
              <div>
                <dt>Признаков</dt>
                <dd>{model.data.features.length}</dd>
              </div>
              {Object.entries(model.data.metrics).map(([k, v]) => (
                <div key={k}>
                  <dt>{METRIC_NAME[k] ?? k}</dt>
                  <dd>{v.toFixed(3).replace('.', ',')}</dd>
                </div>
              ))}
            </dl>
          </>
        )}
      </section>
    </>
  );
}

export function AdminApplication() {
  const { id } = useParams();
  return <ApplicationView id={id!} bank />;
}
