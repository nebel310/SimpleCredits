import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { api, profileComplete, useSession, type Product, type Purpose } from '../../api';
import { useLiveUpdates } from '../../api/ws';
import { useAction, useQuery } from '../../lib/hooks';
import { loadProducts } from '../../lib/catalog';
import { CONSENT_VERSION } from '../../lib/consents';
import { demoByEmail } from '../../lib/demo';
import { money, months, monthsUpTo, newKey, rate, short } from '../../lib/format';
import { LEGAL_FORM_NAME, PURPOSE_NAME, SEGMENT_NAME, TRACK } from '../../lib/labels';
import { annuityPayment, applicantFrom, mismatchReasons, pickProduct, type Applicant } from '../../lib/rules';
import { Btn, Check, ErrorState, Loading, MoneyField, PageTitle, SelectField, StatusBanner, TextField, Tracker, toast } from '../../ui/kit';

// Новая заявка — одна форма (USERFLOW, шаг 5). Банк сразу проверяет данные и оценивает риск.

const ALL_PURPOSES = Object.keys(PURPOSE_NAME) as Purpose[];
const PROGRESS = TRACK.slice(0, 4);

/** Причины, которые клиент не может поменять в форме: сегмент, форма компании, возраст */
const structural = (p: Product, a: Applicant) => mismatchReasons(p, { ...a, purpose: p.purposes[0], amount: p.min_amount_rub, term: p.min_term_months });

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
  const [personalDataConsent, setPersonalDataConsent] = useState(false);
  const [creditHistoryConsent, setCreditHistoryConsent] = useState(false);
  const [tried, setTried] = useState(false);
  const [step, setStep] = useState(0);
  // Ключ попытки: повтор той же заявки (двойной клик, повтор после сбоя сети) не создаст вторую
  const [attemptKey, setAttemptKey] = useState(newKey);
  useEffect(() => setAttemptKey(newKey()), [code, amount, term, purpose]);

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
    if (!p.purposes.includes(purpose)) setPurpose(p.purposes[0]);
    setAmount((a) => (a === null ? p.min_amount_rub : Math.min(p.max_amount_rub, Math.max(p.min_amount_rub, a))));
    setTerm((t) => (t === null ? p.min_term_months : Math.min(p.max_term_months, Math.max(p.min_term_months, t))));
  }

  // Пока банк обрабатывает заявку, показываем этапы по событиям WebSocket
  useLiveUpdates((m) => {
    if (!submit.pending) return;
    if (m.type === 'event' && m.event_type === 'enriched') setStep(2);
    if (m.type === 'status_changed') setStep(3);
  });

  const submit = useAction(async () => {
    setStep(1);
    try {
      const app = await api.createApplication(
        { product_type: product?.product_type ?? null, requested_amount_rub: amount!, term_months: term!, purpose, segment: applicant!.segment,
          consents: { personal_data_processing: personalDataConsent, credit_history_request: creditHistoryConsent, version: CONSENT_VERSION } },
        attemptKey,
      );
      setStep(4);
      nav(`/applications/${app.application_id}`, { replace: true });
    } catch (e) {
      // Заявка сохранена, но проверка не завершилась — ведём в карточку, там можно повторить проверку
      const saved = (e as { data?: { application_id?: unknown } }).data?.application_id;
      if (typeof saved === 'string') {
        toast('Проверка не завершилась, но заявка сохранена — повторите проверку в карточке', true);
        nav(`/applications/${saved}`, { replace: true });
        return;
      }
      throw e;
    }
  });

  if (!user) return null;
  if (!profileComplete(user)) {
    return (
      <>
        <PageTitle crumbs="Заявки" title="Новая заявка" />
        <StatusBanner kind="action" icon="doc" title="Сначала заполните профиль компании" actions={<Btn view="accent" to="/profile?next=apply">Заполнить профиль</Btn>}>
          Для заявки нужны реквизиты и финансы компании. Их заполняют один раз — дальше они подставляются сами.
        </StatusBanner>
      </>
    );
  }

  const c = user.company!;
  const f = user.financials!;
  const list = products.data ?? [];
  const base = applicantFrom(c, f, purpose, amount ?? 0, term ?? 0);
  const applicant = amount && term ? base : null;
  const segment = base.segment;
  const reasons = product && applicant ? mismatchReasons(product, applicant) : [];
  // что подберёт банк — показываем на карточке «Подобрать за меня», даже когда выбран конкретный продукт
  const autoPick = applicant ? pickProduct(list, applicant) : null;
  const auto = product ? null : autoPick;
  const target = product ?? auto;

  // Без выбранного продукта — общие границы всего каталога, чтобы банк смог что-то подобрать
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
  const consentsGiven = personalDataConsent && creditHistoryConsent;
  const valid = !err.amount && !err.term && reasons.length === 0 && consentsGiven;
  const payMin = target && amount && term ? annuityPayment(amount, target.rate_min_percent, term) : null;
  const payMax = target && amount && term ? annuityPayment(amount, target.rate_max_percent, term) : null;

  return (
    <>
      <PageTitle crumbs="Заявки › Новая" title="Новая заявка" />
      {submit.pending ? (
        <section className="card big" aria-live="polite">
          <h2 className="h2">Рассматриваем заявку</h2>
          <Tracker index={step} labels={PROGRESS} sub="сейчас" />
          <span className="muted">Проверяем компанию в ЕГРЮЛ, ФНС и БКИ и оцениваем риск. Обычно это несколько секунд.</span>
        </section>
      ) : (
        <div className="row">
          <section className="card big grow">
            <div className="stack-s">
              <h2 className="h2">Продукт</h2>
              <span className="small muted">Не уверены — оставьте «Подобрать за меня», банк выберет подходящий продукт с самой низкой ставкой.</span>
            </div>
            {products.error && <ErrorState error={products.error} onRetry={() => products.reload()} />}
            {!products.data && !products.error && <Loading lines={2} />}
            {products.data && (
              <div className="grid-fields">
                <button type="button" className="choice" aria-pressed={code === 'auto'} onClick={() => pick(null)}>
                  <b>Подобрать за меня</b>
                  <small>{autoPick ? `Подойдёт: ${autoPick.name}, от ${rate(autoPick.rate_min_percent)}` : 'Под эти условия продукта нет — измените сумму, срок или цель'}</small>
                </button>
                {products.data.map((p) => {
                  const blocked = structural(p, base);
                  return (
                    <button key={p.code} type="button" className="choice" aria-pressed={code === p.code} onClick={() => pick(p)} disabled={blocked.length > 0} title={blocked.length ? `Не подходит: ${blocked.join('; ')}` : undefined}>
                      <b>{p.name}</b>
                      <small>
                        {short(p.min_amount_rub)} — {short(p.max_amount_rub)} · до {monthsUpTo(p.max_term_months)} · от {rate(p.rate_min_percent)}
                      </small>
                      {blocked.length > 0 && <small className="choice-why">Не подходит: {blocked.join('; ')}</small>}
                    </button>
                  );
                })}
              </div>
            )}
            <div className="grid-fields">
              <MoneyField label="Сумма" value={amount} onChange={setAmount} error={tried ? err.amount : null} hint={lim ? `От ${money(lim.aMin)} до ${money(lim.aMax)}` : 'Целое число рублей'} />
              <TextField label="Срок, месяцев" value={term === null ? '' : String(term)} inputMode="numeric" onChange={(v) => setTerm(v.replace(/\D/g, '') ? Number(v.replace(/\D/g, '').slice(0, 3)) : null)} error={tried ? err.term : null} hint={lim ? `От ${lim.tMin} до ${lim.tMax}` : undefined} />
              <SelectField label="Цель" value={purpose} options={purposes.map((p) => ({ value: p, label: PURPOSE_NAME[p] }))} onChange={setPurpose} />
            </div>
            <div className="info-box">
              <b>Сегмент: {SEGMENT_NAME[segment].toLowerCase()}.</b> Его определяет банк по данным профиля: {c.employee_count} сотрудников, выручка {short(f.annual_revenue_rub)} в год. Микробизнес — до 15 сотрудников и до 120 млн ₽ выручки.
            </div>
            {product && reasons.length > 0 && <div className="warn-box">«{product.name}» не подходит под заявку: {reasons.join('; ')}.</div>}
            <div className="panel">
              <span style={{ fontWeight: 600, fontSize: 14 }}>Согласия</span>
              <Check
                checked={personalDataConsent}
                onChange={setPersonalDataConsent}
                label="Согласие на обработку персональных данных"
                hint="Нужно, чтобы проверить заявку и данные компании. Согласие можно отозвать после рассмотрения."
              />
              <Check
                checked={creditHistoryConsent}
                onChange={setCreditHistoryConsent}
                label="Согласие на запрос кредитной истории в БКИ"
                hint="Один запрос при рассмотрении этой заявки. Без подписки и автосписаний."
              />
              {tried && !consentsGiven && (
                <span className="small" style={{ color: 'var(--c-negative-ink)', fontWeight: 600 }}>
                  Отметьте оба согласия, чтобы отправить заявку
                </span>
              )}
            </div>
            {submit.error && <ErrorState error={submit.error.status === 502 || submit.error.status === 504 ? 'Сервис оценки сейчас недоступен. Попробуйте отправить ещё раз чуть позже.' : submit.error} onRetry={() => submit.run()} />}
            <div className="btn-row">
              <Btn
                view="accent"
                disabled={!products.data}
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
                  <dd>{product ? product.name : auto ? `${auto.name} — подберёт банк` : 'Подберёт банк'}</dd>
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
                {payMin !== null && payMax !== null && (
                  <div>
                    <dt style={{ color: '#fff' }}>Платёж в месяц</dt>
                    <dd>
                      {money(payMin)} — {money(payMax)}
                    </dd>
                  </div>
                )}
              </dl>
              {target && (
                <span className="xs">
                  Ставка по продукту — от {rate(target.rate_min_percent)} до {rate(target.rate_max_percent)} годовых: точная зависит от оценки риска. Платёж — предварительный расчёт.
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
              <span className="xs muted">В заявку уйдёт снимок профиля на момент отправки. Кредитную историю банк запросит в БКИ.</span>
            </section>
          </aside>
        </div>
      )}
    </>
  );
}
