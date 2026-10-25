import { useQuery } from '../../lib/hooks';
import { loadProducts } from '../../lib/catalog';
import { short, months, pct } from '../../lib/format';
import { PURPOSE_NAME } from '../../lib/labels';
import { Btn, Chip, ErrorState, Loading, PageTitle } from '../../ui/kit';

const SEGMENT_TEXT = { micro: 'Микробизнес', small: 'Малый бизнес', both: 'Микро и малый бизнес' } as const;

export function Products() {
  const q = useQuery(loadProducts, []);
  return (
    <>
      <PageTitle crumbs="Каталог" title="Кредитные продукты" />
      <span className="muted">Можно выбрать продукт или подать заявку без выбора — тогда банк подберёт его сам.</span>
      {q.error && <ErrorState error={q.error} onRetry={() => q.reload()} />}
      {!q.data && !q.error && <Loading lines={5} />}
      {q.data && (
        <div className="grid-3">
          {q.data.map((p) => (
            <section key={p.code} className="card">
              <div className="row-c between">
                <h2 className="h2">{p.name}</h2>
                <Chip kind="neutral">{SEGMENT_TEXT[p.segment]}</Chip>
              </div>
              <p style={{ margin: 0 }}>{p.description}</p>
              <dl className="dl">
                <div>
                  <dt>Сумма</dt>
                  <dd>
                    {short(p.min_amount_rub)} — {short(p.max_amount_rub)}
                  </dd>
                </div>
                <div>
                  <dt>Срок</dt>
                  <dd>
                    {p.min_term_months}—{months(p.max_term_months)}
                  </dd>
                </div>
                <div>
                  <dt>Ставка</dt>
                  <dd>
                    {pct(p.rate_min_percent, 0)}—{pct(p.rate_max_percent, 0)} годовых
                  </dd>
                </div>
              </dl>
              {p.features.length > 0 && (
                <div className="row-c" style={{ gap: 6 }}>
                  {p.features.map((f) => (
                    <Chip key={f} kind="high">
                      {f}
                    </Chip>
                  ))}
                </div>
              )}
              <div className="small">
                <b>Подходит для:</b> {p.purposes.map((x) => PURPOSE_NAME[x]?.toLowerCase() ?? x).join(', ')}
              </div>
              {p.requirements.length > 0 && <div className="small muted">Требования: {p.requirements.join('; ')}</div>}
              <div style={{ marginTop: 'auto' }}>
                <Btn view="outlined" size={40} to={`/apply?product=${p.code}`}>
                  Подать заявку
                </Btn>
              </div>
            </section>
          ))}
        </div>
      )}
    </>
  );
}
