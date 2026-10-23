import { useEffect, useMemo, useState, type ReactNode } from 'react';
import { Navigate, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { api, ApiError, type ApplicationView, type BusinessGoal, type ChancesResult, type Company, type ExtractedField, type ProductCode } from '../../api';
import { GOALS, PRODUCTS, productByCode } from '../../api/catalog';
import { useAction, useQuery, useSession } from '../../lib/hooks';
import { date, dateTime, money, pct, time } from '../../lib/format';
import { ROLE_NAME } from '../../lib/status';
import { monthlyLoad, overdraftCost, termOptions } from '../../lib/calc';
import { AiHint, Btn, Chip, ErrorState, FileBox, FileDrop, Loading, MoneyField, PageTitle, RadioGroup, RoleGuard, SelectField, SourceTag, TextField, Tracker, toast, Check } from '../../ui/kit';
import { Px } from '../../ui/Px';
import { useAiScreen } from '../../ai/AiAssistant';
import { COMPANY_SHORT } from '../../lib/companies';

const STEPS = ['goal', 'company', 'finance', 'review'] as const;
type Step = (typeof STEPS)[number];
const STEP_LABEL = ['1 · Цель', '2 · Компания', '3 · Финансы', '4 · Подтверждение'];

export function Wizard() {
  const { step = 'goal' } = useParams();
  const [params] = useSearchParams();
  const { session, user } = useSession();
  const [app, setApp] = useState<ApplicationView | null>(null);
  const [err, setErr] = useState<ApiError | null>(null);
  const chances = useQuery(() => api.getChances(session!, user!.companyId!), [user?.companyId], { live: false });

  // Черновик: найти существующий или создать
  useEffect(() => {
    if (user?.role === 'viewer') return;
    let alive = true;
    (async () => {
      try {
        const list = await api.listApplications(session!);
        const d = list.find((a) => a.status === 'DRAFT');
        const qp = params.get('product') as ProductCode | null;
        const qa = params.get('amount');
        let v: ApplicationView;
        if (d && !qp) v = await api.getApplication(session!, d.id);
        else {
          const prod = qp ?? 'working_capital';
          const p = productByCode(prod);
          const goal = GOALS.find((g) => g.product === prod)?.id ?? 'purchase';
          v = await api.createDraft(session!, { product: prod, goal, amount: qa ? Math.min(p.amountMax, Math.max(p.amountMin, Number(qa))) : p.amountMin * 2, termMonths: termOptions(prod)[Math.min(1, termOptions(prod).length - 1)], when: 'week' });
        }
        if (alive) setApp(v);
      } catch (e) {
        if (alive) setErr(e as ApiError);
      }
    })();
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Живое обновление черновика (распознавание выписки идёт в фоне)
  useEffect(() => {
    if (!app) return;
    return api.onChange(() => {
      api.getApplication(session!, app.id).then(setApp).catch(() => undefined);
    });
  }, [app?.id, session]);

  if (user?.role === 'viewer') {
    return (
      <>
        <PageTitle crumbs="Заявки › Новая заявка" title="Новая заявка" />
        <RoleGuard allowed={false} role={user.role} what="Создать заявку">
          {null}
        </RoleGuard>
      </>
    );
  }
  if (!STEPS.includes(step as Step)) return <Navigate to="/apply/goal" replace />;
  if (err) return <ErrorState error={err} />;
  if (!app) return <Loading lines={6} />;
  if (app.status !== 'DRAFT') return <Navigate to={`/applications/${app.id}`} replace />;

  const idx = STEPS.indexOf(step as Step);
  return (
    <>
      <PageTitle crumbs={`Заявки › Новая заявка № ${app.number}`} title="Новая заявка" right={<span className="small muted">Черновик сохраняется сам · {time(app.updatedAt)}</span>} />
      <Tracker index={idx} labels={STEP_LABEL} />
      {app.delegatedToAccountant && user!.role === 'owner' && step === 'finance' && <div className="info-box">Вы передали финансы бухгалтеру. Можно дождаться его или заполнить самому — черновик общий.</div>}
      {app.delegatedToAccountant && user!.role === 'accountant' && <div className="info-box"><b>Задача от владельца:</b> заполнить финансы. Отправит заявку владелец.</div>}
      {step === 'goal' && <GoalStep app={app} setApp={setApp} chances={chances.data} />}
      {step === 'company' && <CompanyStep app={app} setApp={setApp} />}
      {step === 'finance' && <FinanceStep app={app} setApp={setApp} />}
      {step === 'review' && <ReviewStep app={app} setApp={setApp} />}
      <p className="xs muted" style={{ margin: 0 }}>
        Прототип для Альфа-Хак 2026 · данные синтетические
      </p>
    </>
  );
}

interface StepProps {
  app: ApplicationView;
  setApp: (a: ApplicationView) => void;
}

function Layout({ main, side }: { main: ReactNode; side: ReactNode }) {
  return (
    <div className="row">
      <section className="card big grow">{main}</section>
      <aside className="side stack">{side}</aside>
    </div>
  );
}

function Summary({ app, extra }: { app: ApplicationView; extra?: ReactNode }) {
  const p = productByCode(app.product);
  const load = monthlyLoad(app.product, app.amount, app.termMonths);
  return (
    <section className="card red-card">
      <h2 className="h3">Ваша заявка</h2>
      <dl className="dl" style={{ color: '#fff' }}>
        <div>
          <dt style={{ color: '#fff' }}>Продукт</dt>
          <dd>{p.name}</dd>
        </div>
        <div>
          <dt style={{ color: '#fff' }}>{p.kind === 'limit' ? 'Лимит' : 'Сумма'}</dt>
          <dd>{money(app.amount)}</dd>
        </div>
        <div>
          <dt style={{ color: '#fff' }}>Срок</dt>
          <dd>{app.termMonths} мес</dd>
        </div>
        {extra}
        <div className="sep" style={{ borderColor: 'var(--c-black)' }}>
          <dt style={{ color: '#fff' }}>{p.kind === 'limit' ? 'При использовании 50% лимита' : 'Примерный платёж'}</dt>
          <dd className="num">≈ {money(load)}/мес</dd>
        </div>
      </dl>
      <span className="xs">
        Ставка {p.ratePct}% {p.kind === 'limit' ? 'годовых за дни использования' : 'годовых'} — модельная, для примера
      </span>
    </section>
  );
}

// ───────── Шаг 1: цель ─────────

function GoalStep({ app, setApp, chances }: StepProps & { chances?: ChancesResult }) {
  const { session } = useSession();
  const nav = useNavigate();
  const [goal, setGoal] = useState<BusinessGoal>(app.goal);
  const [product, setProduct] = useState<ProductCode>(app.product);
  const [amount, setAmount] = useState<number | null>(app.amount);
  const [term, setTerm] = useState(app.termMonths);
  const [when, setWhen] = useState(app.when);
  const [compare, setCompare] = useState(false);
  const p = productByCode(product);
  const recommended = GOALS.find((g) => g.id === goal)!.product;
  const ch = chances?.products.find((x) => x.product === product);
  const terms = termOptions(product);

  const amountErr = amount === null ? 'Укажите сумму' : amount < p.amountMin ? `Минимум для продукта — ${money(p.amountMin)}` : amount > p.amountMax ? `Максимум для продукта — ${money(p.amountMax)}` : null;
  const aboveEstimate = !amountErr && ch?.limit && amount! > ch.limit;

  useAiScreen('Новая заявка: цель', {
    appId: app.id,
    chips: ['Какую сумму выбрать?', 'Что такое овердрафт?', 'Чем отличается кредит на развитие?'],
    tip: ch?.limit ? { text: `По оборотам предварительно до ${money(ch.limit)} на «${p.name}». Подсказать комфортную сумму?`, action: 'Какую сумму выбрать?' } : undefined,
  });

  const pickGoal = (g: BusinessGoal) => {
    setGoal(g);
    const rec = GOALS.find((x) => x.id === g)!.product;
    switchProduct(rec);
  };
  const switchProduct = (np: ProductCode) => {
    setProduct(np);
    const pp = productByCode(np);
    const t = termOptions(np);
    if (!t.includes(term)) setTerm(t[Math.min(1, t.length - 1)]);
    if (amount !== null && (amount < pp.amountMin || amount > pp.amountMax)) setAmount(Math.min(pp.amountMax, Math.max(pp.amountMin, amount)));
  };

  const save = useAction(async (_k, go: boolean) => {
    const v = await api.updateDraft(session!, app.id, { goal, product, amount: amount!, termMonths: term, when });
    setApp(v);
    if (go) nav('/apply/company');
  });

  const preview = { ...app, product, amount: amount ?? p.amountMin, termMonths: term };

  return (
    <Layout
      main={
        <>
          <h2 className="h2">На что нужны деньги?</h2>
          <div role="group" aria-label="Задача бизнеса" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(200px, 100%), 1fr))', gap: 12 }}>
            {GOALS.map((g) => (
              <button key={g.id} type="button" className="choice" aria-pressed={goal === g.id} onClick={() => pickGoal(g.id)}>
                {goal === g.id && <Chip kind="lime">Выбрано</Chip>}
                <b>{g.title}</b>
                <small>{g.hint}</small>
              </button>
            ))}
          </div>

          <div className="panel row-panel">
            <Px name={ch?.level === 'high' ? 'check' : ch?.level === 'mid' ? 'up' : 'alert'} size={32} color={ch?.level === 'high' ? 'var(--c-high)' : ch?.level === 'mid' ? 'var(--c-mid)' : 'var(--c-gray)'} />
            <div style={{ flex: '1 1 320px', minWidth: 0 }}>
              <div className="xs muted">{product === recommended ? 'Подходит под задачу' : 'Вы выбрали другой продукт'}</div>
              <div className="h3" style={{ marginTop: 2 }}>
                {p.name}
              </div>
              <div className="small" style={{ marginTop: 4 }}>
                {money(p.amountMin)} – {money(p.amountMax)} · {p.termMin}–{p.termMax} мес · {p.collateral.toLowerCase()}. {p.suits}.
              </div>
            </div>
            <div className="seg" role="group" aria-label="Продукт">
              {PRODUCTS.map((x) => (
                <button key={x.code} type="button" aria-pressed={product === x.code} onClick={() => switchProduct(x.code)}>
                  {x.name.replace('Кредит на развитие', 'На развитие')}
                </button>
              ))}
            </div>
          </div>

          <div className="grid-fields">
            <MoneyField label={p.kind === 'limit' ? 'Лимит' : 'Сумма'} value={amount} onChange={setAmount} error={amountErr} hint={`От ${money(p.amountMin)} до ${money(p.amountMax)}`} />
            <SelectField label="Срок" value={term} options={terms.map((t) => ({ value: t, label: `${t} мес` }))} onChange={setTerm} hint={`От ${p.termMin} до ${p.termMax} мес`} />
            <SelectField
              label="Когда нужны деньги"
              value={when}
              options={[
                { value: 'week', label: 'В течение недели' },
                { value: 'month', label: 'В течение месяца' },
                { value: 'browsing', label: 'Пока просто смотрю' },
              ]}
              onChange={setWhen}
            />
          </div>

          {aboveEstimate && (
            <div className="warn-box">
              Сумма выше предварительной оценки (до {money(ch!.limit)}). Отправить заявку можно — банк рассмотрит запрос и сообщит доступные условия.
            </div>
          )}

          {p.kind === 'limit' ? (
            <div className="info-box">
              <b>Сколько стоит овердрафт.</b> Проценты платятся только за дни, когда вы в минусе. Например, если использовать 1 000 000 ₽ в течение 30 дней — около {money(overdraftCost(1_000_000, 30))}. Ставка {p.ratePct}% годовых — модельная.
            </div>
          ) : (
            <div className="info-box">
              Примерный платёж — <b>{money(monthlyLoad(product, amount ?? p.amountMin, term))} в месяц</b>, ставка {p.ratePct}% годовых (модельная). Точные условия банк сообщит в решении.
            </div>
          )}

          {product !== 'overdraft' && (
            <button type="button" className="linkbtn" style={{ alignSelf: 'flex-start' }} onClick={() => setCompare((x) => !x)} aria-expanded={compare}>
              {compare ? 'Скрыть сравнение' : 'Сравнить с овердрафтом'}
            </button>
          )}
          {compare && product !== 'overdraft' && <CompareOverdraft product={product} amount={amount ?? p.amountMin} term={term} onPick={() => switchProduct('overdraft')} />}

          <div className="btn-row">
            <Btn view="accent" onClick={() => save.run(true)} disabled={!!amountErr} loading={save.pending}>
              Дальше: компания
            </Btn>
            <Btn view="outlined" to="/home">
              На главную
            </Btn>
          </div>
          {save.error && <ErrorState error={save.error} onRetry={() => save.run(true)} />}
        </>
      }
      side={
        <>
          <Summary app={preview as ApplicationView} />
          {ch && (
            <AiHint source={`Предварительная оценка от ${dateTime(chances?.calculatedAt)}`}>
              {ch.limit
                ? `По вашим оборотам на «${p.name}» предварительно до ${money(ch.limit)}. Можно запросить больше — банк рассмотрит запрос и сообщит доступные условия.`
                : ch.level === 'unknown'
                  ? 'Данных для предварительного лимита пока нет. Приложите выписку на шаге «Финансы» — это поможет банку оценить заявку.'
                  : 'Для этого продукта сейчас есть стоп-фактор. Подробности — на главной.'}
            </AiHint>
          )}
        </>
      }
    />
  );
}

function CompareOverdraft({ product, amount, term, onPick }: { product: ProductCode; amount: number; term: number; onPick: () => void }) {
  const a = productByCode(product);
  const o = productByCode('overdraft');
  const limit = Math.min(amount, o.amountMax);
  return (
    <div className="panel">
      <div className="tbl-wrap">
        <table className="tbl">
          <thead>
            <tr>
              <th />
              <th>{a.name}</th>
              <th>Овердрафт</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td className="muted">Как работает</td>
              <td>Вся сумма сразу, платёж каждый месяц</td>
              <td>Лимит на счёте, берёте сколько нужно</td>
            </tr>
            <tr>
              <td className="muted">Сумма</td>
              <td>{money(amount)}</td>
              <td>до {money(limit)}</td>
            </tr>
            <tr>
              <td className="muted">Стоимость</td>
              <td>≈ {money(monthlyLoad(product, amount, term))} в месяц</td>
              <td>≈ {money(overdraftCost(limit * 0.5, 30))} за месяц при 50% использования</td>
            </tr>
            <tr>
              <td className="muted">Подходит для</td>
              <td>{a.suits}</td>
              <td>{o.suits}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <button type="button" className="linkbtn" style={{ alignSelf: 'flex-start' }} onClick={onPick}>
        Выбрать овердрафт — сумма и срок сохранятся
      </button>
    </div>
  );
}

// ───────── Шаг 2: компания ─────────

function CompanyStep({ app, setApp }: StepProps) {
  const { session, user } = useSession();
  const company = useQuery(() => api.getCompany(session!, app.companyId), [app.companyId], { live: false });
  const [inn, setInn] = useState('');
  const [state, setState] = useState<'idle' | 'searching' | 'found' | 'not_found' | 'unavailable' | 'invalid' | 'manual'>(app.companyConfirmed ? 'found' : 'idle');
  const [found, setFound] = useState<Company | null>(null);
  const [msg, setMsg] = useState('');
  const [asOf, setAsOf] = useState<string | undefined>();
  const [note, setNote] = useState(app.manualCompanyNote ?? '');

  useEffect(() => {
    if (company.data && !inn) setInn(company.data.inn);
    if (company.data && app.companyConfirmed === 'registry' && !found) setFound(company.data);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [company.data]);

  useAiScreen('Новая заявка: компания', { appId: app.id, chips: ['Что такое ОКВЭД?', 'Что если в реестре старые данные?'] });

  const search = async () => {
    setState('searching');
    try {
      const r = await api.lookupCompany(session!, app.id, inn);
      setMsg(r.message ?? '');
      setAsOf(r.asOf);
      if (r.status === 'found') {
        setFound(r.company!);
        setState('found');
      } else setState(r.status);
    } catch (e) {
      setMsg((e as ApiError).message);
      setState('unavailable');
    }
  };

  const confirm = useAction(async (_k, how: 'registry' | 'manual') => {
    const v = await api.confirmCompany(session!, app.id, how, how === 'manual' ? note : undefined);
    setApp(v);
    toast(how === 'registry' ? 'Компания подтверждена' : 'Уточнение сохранено');
  });
  const delegate = useAction(async () => {
    const v = await api.updateDraft(session!, app.id, { delegatedToAccountant: true });
    setApp(v);
  });

  const isIp = found?.type === 'IP';
  const ready = !!app.companyConfirmed;

  return (
    <Layout
      main={
        <>
          <h2 className="h2">Ваша компания</h2>
          <div className="row-c" style={{ alignItems: 'flex-start', flexWrap: 'nowrap' }}>
            <div style={{ flex: 1 }}>
              <TextField label="ИНН компании или ИП" value={inn} onChange={(v) => setInn(v.replace(/\D/g, '').slice(0, 12))} inputMode="numeric" error={state === 'invalid' ? msg : null} hint="Остальное подтянем из ЕГРЮЛ/ЕГРИП сами" />
            </div>
            <div style={{ paddingTop: 27 }}>
              <Btn view="secondary" onClick={search} loading={state === 'searching'} disabled={inn.length < 10}>
                Найти
              </Btn>
            </div>
          </div>

          {state === 'searching' && (
            <div className="panel" aria-busy="true">
              <div className="skeleton" style={{ height: 22, width: '50%' }} />
              <div className="skeleton" style={{ height: 14, width: '80%' }} />
              <span className="xs muted">Ищем в реестре ФНС…</span>
            </div>
          )}
          {state === 'not_found' && <ErrorState error={msg} />}
          {state === 'unavailable' && (
            <div className="stack-s">
              <ErrorState error={msg} onRetry={search} saved />
              <button type="button" className="linkbtn" style={{ alignSelf: 'flex-start' }} onClick={() => setState('manual')}>
                Уточнить данные вручную
              </button>
            </div>
          )}

          {state === 'found' && found && (
            <div style={{ border: '2px solid var(--c-black)', borderRadius: 20, padding: 24, display: 'flex', flexDirection: 'column', gap: 18 }}>
              <div className="row-c between">
                <div>
                  <div className="xs muted">{ready ? 'Ваша компания' : 'Это ваша компания?'}</div>
                  <div className="h2" style={{ marginTop: 4 }}>
                    {found.name}
                  </div>
                </div>
                <div className="row-c">
                  <Chip kind="high">Действующая</Chip>
                  {app.companyConfirmed === 'registry' && <Chip kind="dark">Подтверждено</Chip>}
                </div>
              </div>
              <dl className="dl-grid">
                <div>
                  <dt>{isIp ? 'ИНН · ОГРНИП' : 'ИНН · ОГРН'}</dt>
                  <dd>
                    {found.inn} · {found.ogrn}
                  </dd>
                </div>
                <div>
                  <dt>Дата регистрации</dt>
                  <dd>{date(found.regDate)}</dd>
                </div>
                <div>
                  <dt>{isIp ? 'Индивидуальный предприниматель' : 'Руководитель'}</dt>
                  <dd>{found.head}</dd>
                </div>
                <div>
                  <dt>Сотрудников</dt>
                  <dd>{found.employees}</dd>
                </div>
                <div>
                  <dt>Основной ОКВЭД</dt>
                  <dd>
                    {found.okved} · {found.okvedName}
                  </dd>
                </div>
                <div>
                  <dt>Адрес</dt>
                  <dd>{found.address}</dd>
                </div>
              </dl>
              <div className="xs muted">
                Источник: {isIp ? 'ЕГРИП' : 'ЕГРЮЛ'}, данные на {date(asOf ?? app.updatedAt)}. Сведения реестра не подтверждают ваши полномочия — их проверит банк при рассмотрении.
              </div>
              {!ready && (
                <div className="btn-row">
                  <Btn view="primary" onClick={() => confirm.run('registry')} loading={confirm.pending}>
                    Да, это моя компания
                  </Btn>
                  <Btn view="outlined" onClick={() => setState('manual')}>
                    Нет, другая
                  </Btn>
                </div>
              )}
            </div>
          )}

          {state === 'manual' && (
            <div className="panel">
              <b>Уточните данные</b>
              <span className="small muted">Проверьте ИНН выше и нажмите «Найти» ещё раз. Если в реестре устаревшие сведения — опишите, что не так. Банк проверит это при рассмотрении.</span>
              <label className="field">
                <span className="lbl">Что не совпадает</span>
                <textarea className="native" value={note} onChange={(e) => setNote(e.target.value)} placeholder="Например: сменился руководитель 01.10.2026, в реестре ещё старые данные" />
              </label>
              <div className="btn-row">
                <Btn view="primary" onClick={() => confirm.run('manual')} disabled={note.trim().length < 5} loading={confirm.pending}>
                  Сохранить уточнение
                </Btn>
                <button type="button" className="linkbtn muted" onClick={() => setState(found ? 'found' : 'idle')}>
                  Отмена
                </button>
              </div>
            </div>
          )}
          {app.companyConfirmed === 'manual' && <div className="info-box">Данные компании уточнены вручную: «{app.manualCompanyNote}». Банк проверит их при рассмотрении.</div>}

          {user!.role === 'owner' && (
            <div className="panel row-panel">
              <span aria-hidden="true" style={{ width: 44, height: 44, display: 'flex', alignItems: 'center', justifyContent: 'center', background: '#fff', fontWeight: 700 }}>
                БХ
              </span>
              <div style={{ flex: '1 1 320px' }}>
                <b>Финансы может заполнить бухгалтер</b>
                <div className="small muted">Бухгалтер увидит задачу в своём кабинете. Отправляете и подписываете всё равно вы.</div>
              </div>
              {app.delegatedToAccountant ? (
                <Chip kind="mid">Передано · ожидаем заполнения финансов</Chip>
              ) : (
                <Btn view="outlined" size={40} onClick={() => delegate.run()} loading={delegate.pending}>
                  Передать бухгалтеру
                </Btn>
              )}
            </div>
          )}
          {confirm.error && <ErrorState error={confirm.error} />}
          <div className="btn-row">
            <Btn view="accent" to="/apply/finance" disabled={!ready}>
              Дальше: финансы
            </Btn>
            <Btn view="outlined" to="/apply/goal">
              Назад
            </Btn>
            {!ready && <span className="xs muted">Подтвердите компанию или уточните данные вручную</span>}
          </div>
        </>
      }
      side={
        <>
          <Summary app={app} extra={<div><dt style={{ color: '#fff' }}>Компания</dt><dd>{COMPANY_SHORT[app.companyId]}</dd></div>} />
          <AiHint>Проверьте название и руководителя. Если в реестре устаревшие данные, нажмите «Нет, другая» и опишите, что не так — банк проверит. Это не отказ.</AiHint>
        </>
      }
    />
  );
}

// ───────── Шаг 3: финансы ─────────

function FinanceStep({ app, setApp }: StepProps) {
  const { session } = useSession();
  const nav = useNavigate();
  const f = app.finance;
  const [hasLoans, setHasLoans] = useState<'yes' | 'no' | null>(f.hasLoans === null ? null : f.hasLoans ? 'yes' : 'no');
  const [payments, setPayments] = useState<number | null>(f.loanPayments);
  const [guarantor, setGuarantor] = useState(f.guarantor);
  const [gName, setGName] = useState(f.guarantorName);
  const [comment, setComment] = useState(f.comment);
  const [fileErr, setFileErr] = useState<string | null>(null);
  const [fields, setFields] = useState<ExtractedField[]>(f.statement?.fields ?? []);
  const [tried, setTried] = useState(false);

  useEffect(() => {
    setFields(app.finance.statement?.fields ?? []);
  }, [app.finance.statement?.status, app.finance.statement?.fields.length]);

  useAiScreen('Новая заявка: финансы', { appId: app.id, chips: ['Что такое поручитель?', 'Зачем выписка из другого банка?', 'Что такое денежный поток?'] });

  const missing = useMemo(() => {
    const m: string[] = [];
    if (hasLoans === null) m.push('Укажите, есть ли у бизнеса кредиты');
    if (hasLoans === 'yes' && (!payments || payments <= 0)) m.push('Укажите платёж по кредитам в месяц');
    if (f.revenueYear.value === null && app.finance.statement?.status !== 'confirmed') m.push('Отчётности в ФНС нет — приложите выписку и подтвердите поля');
    if (guarantor === 'third_party' && gName.trim().length < 3) m.push('Укажите поручителя');
    if (app.finance.statement && ['extracting', 'check'].includes(app.finance.statement.status)) m.push('Подтвердите поля из выписки или удалите файл');
    return m;
  }, [hasLoans, payments, f.revenueYear.value, app.finance.statement, guarantor, gName]);

  const save = useAction(async (_k, go: boolean) => {
    const v = await api.updateDraft(session!, app.id, { finance: { hasLoans: hasLoans === null ? null : hasLoans === 'yes', loanPayments: hasLoans === 'yes' ? payments : null, guarantor, guarantorName: gName, comment } });
    setApp(v);
    if (go) nav('/apply/review');
  });
  const upload = useAction(async (_k, file: File) => {
    const v = await api.uploadStatement(session!, app.id, { name: file.name, size: file.size, type: file.type });
    setApp(v);
  });
  const confirmFields = useAction(async () => {
    const v = await api.confirmStatementFields(session!, app.id, fields);
    setApp(v);
    toast('Данные выписки подтверждены');
  });
  const remove = useAction(async () => {
    const v = await api.removeStatement(session!, app.id);
    setApp(v);
  });

  const onFile = (file: File) => {
    setFileErr(null);
    const ext = file.name.split('.').pop()?.toLowerCase() ?? '';
    if (!['pdf', 'xlsx', 'xls', 'csv'].includes(ext)) return setFileErr('Подойдут выписки в PDF, XLSX или CSV');
    if (file.size > 10 * 1024 * 1024) return setFileErr('Файл больше 10 МБ');
    upload.run(file);
  };

  const st = app.finance.statement;
  const trend = f.inflowTrendPct.value ?? 0;

  return (
    <Layout
      main={
        <>
          <h2 className="h2">Финансы</h2>
          <div className="grid-2" style={{ gap: 16 }}>
            <div className="panel">
              <div className="row-c between">
                <span className="small muted">Выручка за год</span>
                <SourceTag origin={f.revenueYear.origin} />
              </div>
              <span className="h2">{f.revenueYear.value === null ? 'Нет данных' : money(f.revenueYear.value)}</span>
              <span className="xs muted">
                {f.revenueYear.source}, на {date(f.revenueYear.asOf)}
              </span>
            </div>
            <div className="panel">
              <div className="row-c between">
                <span className="small muted">Поступления на счёт, в среднем в месяц</span>
                <SourceTag origin={f.inflows3m.origin} />
              </div>
              <span className="h2">{money(f.inflows3m.value)}</span>
              <span className="xs" style={{ color: trend < -10 ? 'var(--c-negative-ink)' : 'var(--c-text-2)', fontWeight: trend < -10 ? 600 : 400 }}>
                {trend < 0 ? `За 3 месяца: −${pct(Math.abs(trend), 0)}` : trend > 0 ? `За 3 месяца: +${pct(trend, 0)}` : 'Без изменений'} · {f.inflows3m.source}, на {date(f.inflows3m.asOf)}
              </span>
            </div>
          </div>
          {f.revenueYear.value === null && <div className="warn-box">Отчётности в ФНС ещё нет. Приложите выписку по счетам ниже — без неё банк не сможет оценить выручку.</div>}

          <div className="field">
            <span className="lbl">Есть ли у бизнеса кредиты и лизинг сейчас?</span>
            <RadioGroup
              name="loans"
              row
              value={hasLoans}
              onChange={setHasLoans}
              options={[
                { value: 'yes', label: 'Есть' },
                { value: 'no', label: 'Нет' },
              ]}
            />
            {tried && hasLoans === null && <span className="err">Выберите вариант</span>}
          </div>
          {hasLoans === 'yes' && (
            <div style={{ maxWidth: 360 }}>
              <MoneyField label="Платёж по всем кредитам в месяц" value={payments} onChange={setPayments} error={tried && (!payments || payments <= 0) ? 'Укажите сумму больше нуля' : null} hint="Вы указали · банк сверит с кредитной историей" />
            </div>
          )}

          <div className="field">
            <span className="lbl">Поручитель</span>
            <RadioGroup
              name="guarantor"
              value={guarantor}
              onChange={setGuarantor}
              options={[
                { value: 'none', label: 'Без поручителя' },
                { value: 'owner', label: 'Владелец бизнеса', hint: 'Владелец тоже подпишет договор поручительства' },
                { value: 'third_party', label: 'Другой человек или компания' },
              ]}
            />
          </div>
          {guarantor === 'third_party' && (
            <div style={{ maxWidth: 420 }}>
              <TextField label="Кто поручитель" value={gName} onChange={setGName} hint="ФИО или название компании. Банк пришлёт поручителю задачу в кабинете" error={tried && gName.trim().length < 3 ? 'Укажите поручителя' : null} />
            </div>
          )}

          <label className="field">
            <span className="lbl">Комментарий для банка</span>
            <textarea className="native" value={comment} onChange={(e) => setComment(e.target.value)} placeholder="Например: сезонный спад, в ноябре поступления вернутся" />
            <span className="hint">Банк увидит комментарий при рассмотрении</span>
          </label>

          <div className="stack-s">
            <div className="row-c between">
              <b>Выписка из другого банка</b>
              <span className="xs muted">{f.revenueYear.value === null ? 'обязательно для вашей заявки' : 'по желанию'}</span>
            </div>
            <span className="small muted">Если часть оборотов идёт через другой банк, выписка поможет уточнить оценку. Цифры распознаем сами — вы только проверите.</span>
            {!st && <FileDrop onFile={onFile} formats={['PDF', 'XLSX', 'CSV']} maxMb={10} disabled={upload.pending} />}
            {upload.pending && (
              <div className="info-box">
                <span className="spin" style={{ width: 14, height: 14, marginRight: 8 }} /> Загружаем файл…
              </div>
            )}
            {(fileErr || upload.error) && <ErrorState error={fileErr ?? upload.error!} />}
            {st && (
              <>
                <FileBox
                  name={st.file.name}
                  size={st.file.size}
                  uploadedAt={st.file.uploadedAt}
                  right={
                    <div className="row-c">
                      <Chip kind={st.status === 'confirmed' ? 'high' : st.status === 'extracting' ? 'mid' : st.status === 'error' ? 'low' : 'attention'}>
                        {st.status === 'extracting' ? 'Распознаём' : st.status === 'check' ? 'Проверьте поля' : st.status === 'confirmed' ? 'Подтверждено' : 'Ошибка'}
                      </Chip>
                      <button type="button" className="linkbtn muted" onClick={() => remove.run()}>
                        {st.status === 'confirmed' ? 'Заменить' : 'Удалить'}
                      </button>
                    </div>
                  }
                />
                {st.status === 'extracting' && (
                  <div className="ai-hint" style={{ padding: 16 }}>
                    <div className="ttl">
                      <span className="spin" style={{ width: 14, height: 14 }} /> ИИ распознаёт выписку…
                    </div>
                  </div>
                )}
                {(st.status === 'check' || st.status === 'confirmed') && (
                  <div className="ai-hint" style={{ padding: 18 }}>
                    <div className="ttl">
                      <Px name="gem" size={16} color="var(--c-ai)" />
                      {st.error ? 'Не удалось распознать — заполните вручную' : 'ИИ распознал поля — проверьте'}
                    </div>
                    {st.error && <span className="small">{st.error}</span>}
                    <div className="grid-fields">
                      {fields.map((fl, i) => (
                        <TextField
                          key={fl.key}
                          label={fl.label}
                          value={fl.value}
                          disabled={st.status === 'confirmed'}
                          onChange={(v) => setFields(fields.map((x, j) => (j === i ? { ...x, value: v } : x)))}
                          hint={st.status === 'confirmed' ? 'Подтверждено вами' : st.error ? 'Вы указали' : 'Из файла'}
                        />
                      ))}
                    </div>
                    {st.status === 'check' && (
                      <div className="btn-row">
                        <Btn view="primary" size={40} onClick={() => confirmFields.run()} loading={confirmFields.pending} disabled={fields.some((x) => !x.value.trim())}>
                          Всё верно, подтвердить
                        </Btn>
                        {confirmFields.error && <span className="xs" style={{ color: 'var(--c-negative-ink)' }}>{confirmFields.error.message}</span>}
                      </div>
                    )}
                  </div>
                )}
              </>
            )}
          </div>

          {tried && missing.length > 0 && (
            <div className="err-box" style={{ flexDirection: 'column', alignItems: 'flex-start' }}>
              <span>Чтобы продолжить, нужно:</span>
              <ul style={{ margin: 0, paddingLeft: 20, fontWeight: 400 }}>
                {missing.map((m) => (
                  <li key={m}>{m}</li>
                ))}
              </ul>
            </div>
          )}
          <div className="btn-row">
            <Btn
              view="accent"
              loading={save.pending}
              onClick={() => {
                setTried(true);
                if (!missing.length) save.run(true);
                else save.run(false);
              }}
            >
              Дальше: подтверждение
            </Btn>
            <Btn view="outlined" to="/apply/company">
              Назад
            </Btn>
          </div>
          {save.error && <ErrorState error={save.error} />}
        </>
      }
      side={
        <>
          <Summary app={app} />
          {trend < -10 ? (
            <AiHint source={`${f.inflows3m.source}, на ${date(f.inflows3m.asOf)}`}>Поступления за последние 3 месяца упали на {Math.abs(trend)}%. Если это сезонность, напишите об этом в комментарии — банк увидит. Если часть оборотов в другом банке — приложите выписку.</AiHint>
          ) : (
            <AiHint>Цифры выручки и оборотов мы уже подтянули из ФНС и вашего счёта. Вам осталось ответить про кредиты и поручителя.</AiHint>
          )}
        </>
      }
    />
  );
}

// ───────── Шаг 4: подтверждение ─────────

function ReviewStep({ app, setApp }: StepProps) {
  const { session, user } = useSession();
  const nav = useNavigate();
  const [bki, setBki] = useState(!!app.consents.bki);
  const [pd, setPd] = useState(!!app.consents.pd);
  const f = app.finance;
  const p = productByCode(app.product);

  useAiScreen('Новая заявка: подтверждение', { appId: app.id, chips: ['Зачем согласие на БКИ?', 'Что будет после отправки?'] });

  const gaps: string[] = [];
  if (!app.companyConfirmed) gaps.push('Компания не подтверждена — шаг 2');
  if (f.hasLoans === null) gaps.push('Не указано, есть ли кредиты — шаг 3');
  if (f.hasLoans && !f.loanPayments) gaps.push('Не указан платёж по кредитам — шаг 3');
  if (f.revenueYear.value === null && f.statement?.status !== 'confirmed') gaps.push('Нужна подтверждённая выписка — шаг 3');
  const needConsents = !app.consents.bki || !app.consents.pd;

  const consents = useAction(async () => {
    const v = await api.giveConsents(session!, app.id);
    setApp(v);
  });
  const submit = useAction(async (key) => {
    const v = await api.submitApplication(session!, app.id, key);
    setApp(v);
    toast('Заявка отправлена');
    nav(`/applications/${v.id}`, { replace: true });
  });

  const canSubmit = user!.role === 'owner';
  const blockReason = !canSubmit ? 'Отправить заявку может владелец' : gaps.length ? 'Заполните пропуски выше' : needConsents ? 'Нужны согласия' : null;

  return (
    <Layout
      main={
        <>
          <h2 className="h2">Проверьте и отправьте</h2>
          <Section title="Цель и параметры" edit="/apply/goal">
            {GOALS.find((g) => g.id === app.goal)?.title} · {p.name} · {money(app.amount)} · {app.termMonths} мес
          </Section>
          <Section title="Компания" edit="/apply/company">
            {COMPANY_SHORT[app.companyId]} · {app.companyConfirmed === 'registry' ? 'подтверждено по реестру' : app.companyConfirmed === 'manual' ? 'уточнено вручную' : <b style={{ color: 'var(--c-negative-ink)' }}>не подтверждено</b>}
          </Section>
          <Section title="Финансы" edit="/apply/finance">
            Выручка {money(f.revenueYear.value)} · поступления {money(f.inflows3m.value)}/мес · кредиты: {f.hasLoans === null ? <b style={{ color: 'var(--c-negative-ink)' }}>не указано</b> : f.hasLoans ? `да, ${money(f.loanPayments)}/мес` : 'нет'} · поручитель: {f.guarantor === 'none' ? 'нет' : f.guarantor === 'owner' ? 'владелец' : f.guarantorName}
            {f.statement && ` · выписка: ${f.statement.status === 'confirmed' ? 'подтверждена' : 'не подтверждена'}`}
          </Section>

          {gaps.length > 0 && (
            <div className="err-box" style={{ flexDirection: 'column', alignItems: 'flex-start' }}>
              <span>Не хватает данных:</span>
              <ul style={{ margin: 0, paddingLeft: 20, fontWeight: 400 }}>
                {gaps.map((g) => (
                  <li key={g}>{g}</li>
                ))}
              </ul>
            </div>
          )}

          <div className="panel">
            <b>Согласия</b>
            {app.consents.bki ? (
              <div className="row-c small">
                <Px name="check" size={14} color="var(--c-high)" /> Согласие на запрос в БКИ дано {dateTime(app.consents.bki.at)} · {app.consents.bki.by}
              </div>
            ) : (
              <Check checked={bki} onChange={setBki} disabled={!canSubmit} label="Согласен на запрос в бюро кредитных историй (218-ФЗ)" hint="Без него банк не может проверить кредитную историю" />
            )}
            {app.consents.pd ? (
              <div className="row-c small">
                <Px name="check" size={14} color="var(--c-high)" /> Согласие на обработку персональных данных дано {dateTime(app.consents.pd.at)} · {app.consents.pd.by}
              </div>
            ) : (
              <Check checked={pd} onChange={setPd} disabled={!canSubmit} label="Согласен на обработку персональных данных (152-ФЗ)" />
            )}
            {needConsents && canSubmit && (
              <div>
                <Btn view="primary" size={40} disabled={!(bki || app.consents.bki) || !(pd || app.consents.pd)} loading={consents.pending} onClick={() => consents.run()}>
                  Сохранить согласия
                </Btn>
              </div>
            )}
            {!canSubmit && needConsents && <span className="small muted">Согласия даёт владелец.</span>}
          </div>

          <div className="panel">
            <b>Что будет после отправки</b>
            <ol style={{ margin: 0, paddingLeft: 20 }} className="small">
              <li>Начнём проверку данных: реестр, налоги, кредитная история, суды.</li>
              <li>Посчитаем оценку по правилам. Иногда банк просит документ или проверяет заявку вручную — это не отказ.</li>
              <li>Статус появится в кабинете. Писем и SMS не будет.</li>
            </ol>
          </div>

          <div className="small">
            Отправляет: <b>{user!.name}</b>, {ROLE_NAME[user!.role].toLowerCase()} · {COMPANY_SHORT[app.companyId]}
          </div>
          {!canSubmit && (
            <RoleGuard allowed={false} role={user!.role} what="Отправить заявку">
              {null}
            </RoleGuard>
          )}
          {submit.error && <ErrorState error={submit.error} onRetry={() => submit.run()} saved />}
          <div className="btn-row">
            <Btn view="accent" onClick={() => submit.run()} loading={submit.pending} disabled={!!blockReason}>
              {submit.pending ? 'Отправляем…' : 'Отправить заявку'}
            </Btn>
            <Btn view="outlined" to="/apply/finance">
              Назад
            </Btn>
            {blockReason && <span className="xs muted">{blockReason}</span>}
          </div>
        </>
      }
      side={
        <>
          <Summary app={app} extra={<div><dt style={{ color: '#fff' }}>Подписывает</dt><dd>Владелец</dd></div>} />
          <AiHint>Согласие на запрос в бюро нужно по закону: без него банк не может посмотреть кредитную историю. Если что-то непонятно — выделите текст и спросите меня.</AiHint>
        </>
      }
    />
  );
}

function Section({ title, edit, children }: { title: string; edit: string; children: ReactNode }) {
  const nav = useNavigate();
  return (
    <div className="row-c between" style={{ padding: '14px 0', borderTop: '1px solid var(--c-line)', flexWrap: 'nowrap', alignItems: 'flex-start' }}>
      <div style={{ minWidth: 0 }}>
        <div className="xs muted">{title}</div>
        <div>{children}</div>
      </div>
      <button type="button" className="linkbtn" onClick={() => nav(edit)}>
        Изменить
      </button>
    </div>
  );
}
