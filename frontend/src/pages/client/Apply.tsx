import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { api, profileComplete, useSession, type Product, type Purpose, type Segment } from '../../api';
import { useLiveUpdates } from '../../api/ws';
import { useAction, useQuery } from '../../lib/hooks';
import { loadProducts } from '../../lib/catalog';
import { demoByEmail } from '../../lib/demo';
import { money, months, monthsUpTo, short } from '../../lib/format';
import { LEGAL_FORM_NAME, PURPOSE_NAME, SEGMENT_NAME } from '../../lib/labels';
import { Btn, ErrorState, Loading, MoneyField, PageTitle, RadioGroup, SelectField, StatusBanner, TextField, Tracker } from '../../ui/kit';

// Новая заявка — одна форма (USERFLOW, шаг 5). Бэкенд сразу проверяет данные и считает скоринг.

const ALL_PURPOSES = Object.keys(PURPOSE_NAME) as Purpose[];
const PROGRESS = ['Отправляем заявку', 'ЕГРЮЛ, ФНС, БКИ', 'Скоринг', 'Решение'];

export function Apply() {
  const user = useSession((s) => s.user);
  const nav = useNavigate();
  const [params] = useSearchParams();
  const products = useQuery(loadProducts, []);
  const preset = demoByEmail(user?.email)?.application;

  const [code, setCode] = useState<string>('auto');
  const [amount, setAmount] = useState<number | null>(preset?.requested_amount_rub ?? 1_000_000);
  const [term, setTerm] = useState<number | null>(preset?.term_months ?? 12);
  const [purpose, setPurpose] = useState<Purpose>(preset?.purpose ?? 'working_capital');
  const [segment, setSegment] = useState<Segment>(preset?.segment ?? 'small');
  const [tried, setTried] = useState(false);
  const [step, setStep] = useState(0);

  // Продукт и параметры из ссылки (?product=&amount=&term=&purpose=) или из демо-сценария
  useEffect(() => {
    const list = products.data;
    if (!list) return;
    const fromUrl = params.get('product');
    const p = fromUrl ? list.find((x) => x.code === fromUrl) : preset?.product_type ? list.find((x) => x.product_type === preset.product_type) : undefined;
    if (p) pick(p);
    const a = Number(params.get('amount'));
    if (a > 0) setAmount(a);
    const t = Number(params.get('term'));
    if (t > 0) setTerm(t);
    const pu = params.get('purpose') as Purpose | null;
    if (pu && ALL_PURPOSES.includes(pu)) setPurpose(pu);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [products.data]);

  const product = useMemo(() => products.data?.find((p) => p.code === code), [products.data, code]);
  const purposes = product ? product.purposes : ALL_PURPOSES;

  function pick(p: Product | null) {
    setCode(p ? p.code : 'auto');
    if (!p) return;
    if (p.segment !== 'both') setSegment(p.segment);
    if (!p.purposes.includes(purpose)) setPurpose(p.purposes[0]);
    setAmount((a) => (a === null ? p.min_amount_rub : Math.min(p.max_amount_rub, Math.max(p.min_amount_rub, a))));
    setTerm((t) => (t === null ? p.min_term_months : Math.min(p.max_term_months, Math.max(p.min_term_months, t))));
  }

  // Пока бэкенд обрабатывает заявку, показываем этапы по событиям WebSocket
  useLiveUpdates((m) => {
    if (!submit.pending) return;
    if (m.type === 'event' && m.event_type === 'enriched') setStep(2);
    if (m.type === 'status_changed') setStep(3);
  });

  const submit = useAction(async () => {
    setStep(1);
    const app = await api.createApplication({ product_type: product?.product_type ?? null, requested_amount_rub: amount!, term_months: term!, purpose, segment });
    setStep(4);
    nav(`/applications/${app.application_id}`);
  });

  if (!user) return null;
  if (!profileComplete(user)) {
    return (
      <>
        <PageTitle crumbs="Заявки" title="Новая заявка" />
        <StatusBanner kind="action" icon="doc" title="Сначала заполните профиль компании" actions={<Btn view="accent" to="/profile?next=apply">Заполнить профиль</Btn>}>
          Для заявки нужны реквизиты, финансы и кредитная история компании. Их заполняют один раз — дальше они подставляются сами.
        </StatusBanner>
      </>
    );
  }

  // Без выбранного продукта — общие границы всего каталога, чтобы банк смог что-то подобрать
  const list = products.data ?? [];
  const lim = product
    ? { aMin: product.min_amount_rub, aMax: product.max_amount_rub, tMin: product.min_term_months, tMax: product.max_term_months, who: `Для продукта «${product.name}»` }
    : list.length
      ? { aMin: Math.min(...list.map((p) => p.min_amount_rub)), aMax: Math.max(...list.map((p) => p.max_amount_rub)), tMin: Math.min(...list.map((p) => p.min_term_months)), tMax: Math.max(...list.map((p) => p.max_term_months)), who: 'По нашим продуктам' }
      : null;
  const err = {
    amount:
      amount === null || amount <= 0
        ? 'Укажите сумму'
        : lim && (amount < lim.aMin || amount > lim.aMax)
          ? `${lim.who} — от ${money(lim.aMin)} до ${money(lim.aMax)}`
          : null,
    term:
      term === null || term < 1
        ? 'Укажите срок'
        : lim && (term < lim.tMin || term > lim.tMax)
          ? `${lim.who} — от ${lim.tMin} до ${monthsUpTo(lim.tMax)}`
          : null,
  };
  const valid = !err.amount && !err.term;
  const c = user.company!;
  const f = user.financials!;

  return (
    <>
      <PageTitle crumbs="Заявки › Новая" title="Новая заявка" />
      {submit.pending ? (
        <section className="card big" aria-live="polite">
          <h2 className="h2">Рассматриваем заявку</h2>
          <Tracker index={step} labels={PROGRESS} />
          <span className="muted">Бэкенд проверяет компанию в ЕГРЮЛ, ФНС и БКИ и отправляет данные в скоринговую модель. Обычно это занимает несколько секунд.</span>
        </section>
      ) : (
        <div className="row">
          <section className="card big grow">
            <div className="stack-s">
              <h2 className="h2">Продукт</h2>
              <span className="small muted">Не уверены — оставьте «Подобрать за меня», банк выберет продукт сам.</span>
            </div>
            {products.error && <ErrorState error={products.error} onRetry={() => products.reload()} />}
            {!products.data && !products.error && <Loading lines={2} />}
            {products.data && (
              <div className="grid-fields">
                <button type="button" className="choice" aria-pressed={code === 'auto'} onClick={() => pick(null)}>
                  <b>Подобрать за меня</b>
                  <small>Банк выберет подходящий продукт по сумме и цели</small>
                </button>
                {products.data.map((p) => (
                  <button key={p.code} type="button" className="choice" aria-pressed={code === p.code} onClick={() => pick(p)}>
                    <b>{p.name}</b>
                    <small>
                      {short(p.min_amount_rub)} — {short(p.max_amount_rub)} · до {monthsUpTo(p.max_term_months)}
                    </small>
                  </button>
                ))}
              </div>
            )}
            <div className="grid-fields">
              <MoneyField label="Сумма" value={amount} onChange={setAmount} error={tried ? err.amount : null} hint={lim ? `От ${money(lim.aMin)} до ${money(lim.aMax)}` : 'Целое число рублей'} />
              <TextField label="Срок, месяцев" value={term === null ? '' : String(term)} inputMode="numeric" onChange={(v) => setTerm(v.replace(/\D/g, '') ? Number(v.replace(/\D/g, '').slice(0, 3)) : null)} error={tried ? err.term : null} hint={lim ? `От ${lim.tMin} до ${lim.tMax}` : undefined} />
              <SelectField label="Цель" value={purpose} options={purposes.map((p) => ({ value: p, label: PURPOSE_NAME[p] }))} onChange={setPurpose} />
            </div>
            <div className="stack-s">
              <span style={{ fontWeight: 600, fontSize: 14 }}>Сегмент бизнеса</span>
              <RadioGroup<Segment>
                name="segment"
                row
                value={segment}
                options={(Object.keys(SEGMENT_NAME) as Segment[]).map((s) => ({ value: s, label: SEGMENT_NAME[s] }))}
                onChange={setSegment}
                disabled={!!product && product.segment !== 'both'}
              />
              {product && product.segment !== 'both' && <span className="xs muted">Продукт «{product.name}» — только для сегмента «{SEGMENT_NAME[product.segment].toLowerCase()}»</span>}
            </div>
            {submit.error && (
              <ErrorState
                error={
                  submit.error.status === 502 || submit.error.status === 504
                    ? `Сервис скоринга ${submit.error.status === 504 ? 'не ответил вовремя' : 'недоступен'}. Заявка сохранена со статусом «Ошибка обработки» — её видно в списке заявок. Попробуйте отправить ещё раз чуть позже.`
                    : submit.error
                }
                onRetry={() => submit.run()}
              />
            )}
            <div className="btn-row">
              <Btn
                view="accent"
                onClick={() => {
                  setTried(true);
                  if (valid) submit.run();
                }}
              >
                Отправить заявку
              </Btn>
              <span className="small muted">Решение придёт сразу после проверки</span>
            </div>
          </section>

          <aside className="side stack">
            <section className="card red-card">
              <h2 className="h3">Ваша заявка</h2>
              <dl className="dl" style={{ color: '#fff' }}>
                <div>
                  <dt style={{ color: '#fff' }}>Продукт</dt>
                  <dd>{product ? product.name : 'Подберёт банк'}</dd>
                </div>
                <div>
                  <dt style={{ color: '#fff' }}>Сумма</dt>
                  <dd>{money(amount)}</dd>
                </div>
                <div>
                  <dt style={{ color: '#fff' }}>Срок</dt>
                  <dd>{term ? months(term) : '—'}</dd>
                </div>
                <div className="sep" style={{ borderColor: 'var(--c-black)' }}>
                  <dt style={{ color: '#fff' }}>Цель</dt>
                  <dd>{PURPOSE_NAME[purpose]}</dd>
                </div>
              </dl>
              {product && (
                <span className="xs">
                  Ставка по продукту — от {product.rate_min_percent}% до {product.rate_max_percent}% годовых
                </span>
              )}
            </section>
            <section className="card tight">
              <div className="row-c between">
                <h2 className="h3">Данные компании</h2>
                <Link to="/profile" className="small">
                  Изменить
                </Link>
              </div>
              <dl className="dl">
                <div>
                  <dt>Компания</dt>
                  <dd>{c.legal_name}</dd>
                </div>
                <div>
                  <dt>ИНН · форма</dt>
                  <dd>
                    {c.inn} · {LEGAL_FORM_NAME[c.legal_form]}
                  </dd>
                </div>
                <div>
                  <dt>Выручка за год</dt>
                  <dd>{money(f.annual_revenue_rub)}</dd>
                </div>
                <div>
                  <dt>Выручка в месяц</dt>
                  <dd>{money(f.monthly_revenue_rub)}</dd>
                </div>
              </dl>
              <span className="xs muted">В заявку уйдёт снимок профиля на момент отправки</span>
            </section>
          </aside>
        </div>
      )}
    </>
  );
}
