import { useEffect, useState, type ReactNode } from 'react';
import { Navigate, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import { api, ApiError, type ApplicationView, type BusinessGoal, type ChancesResult, type ProductCode } from '../../api';
import { GOALS, PRODUCTS, productByCode } from '../../api/catalog';
import { useAction, useQuery, useSession } from '../../lib/hooks';
import { dateTime, money, time } from '../../lib/format';
import { monthlyLoad, overdraftCost, termOptions } from '../../lib/calc';
import { AiHint, Btn, Chip, ErrorState, Loading, MoneyField, PageTitle, RoleGuard, SelectField, Tracker } from '../../ui/kit';
import { Px } from '../../ui/Px';
import { useAiScreen } from '../../ai/AiAssistant';

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
      {app.delegatedToAccountant && user!.role === 'accountant' && <div className="info-box"><b>Задача от владельца:</b> заполнить финансы. Отправит заявку владелец.</div>}
      {step === 'goal' && <GoalStep app={app} setApp={setApp} chances={chances.data} />}
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
