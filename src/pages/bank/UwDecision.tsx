import { useEffect, useState } from 'react';
import { Navigate, useNavigate, useParams } from 'react-router-dom';
import { api, type DecisionInput, type ProductCode } from '../../api';
import { PRODUCTS, REASON_CATALOG, productByCode } from '../../api/catalog';
import { useAction, useSession } from '../../lib/hooks';
import { dec2, money } from '../../lib/format';
import { monthlyLoad, termOptions } from '../../lib/calc';
import { PRODUCT_NAME } from '../../lib/status';
import { Btn, Check, Chip, ErrorState, Loading, MoneyField, PageTitle, RadioGroup, SelectField, TextField, toast } from '../../ui/kit';
import { Px } from '../../ui/Px';
import { useAiScreen } from '../../ai/AiAssistant';
import { useBankApp } from './BankApplication';
import { COMPANY_SHORT } from '../../lib/companies';

type Outcome = DecisionInput['outcome'];
const REASON_KEYS = ['AFFORD', 'TREND', 'OVERDUE', 'DEBT_LOAD', 'DATA', 'LIMIT', 'HS1', 'HS2', 'HS3', 'HS4', 'HS5'];

export function UwDecision() {
  const { id } = useParams();
  const { session, user } = useSession();
  const nav = useNavigate();
  const q = useBankApp(id);
  const app = q.data;
  const [outcome, setOutcome] = useState<Outcome>('COUNTER_OFFER');
  const [amount, setAmount] = useState<number | null>(null);
  const [term, setTerm] = useState<number>(12);
  const [product, setProduct] = useState<ProductCode>('working_capital');
  const [reasons, setReasons] = useState<string[]>([]);
  const [text, setText] = useState('');
  const [checked, setChecked] = useState(false);
  const [comment, setComment] = useState('');
  const [doc, setDoc] = useState({ type: 'bank_statement' as const, title: 'Выписка из другого банка', why: '', deadline: 3, comment: '' });
  const [aiErr, setAiErr] = useState<string | null>(null);
  const [aiBusy, setAiBusy] = useState(false);
  useAiScreen('Банк: решение андеррайтера', { appId: id, chips: ['Что такое DSCR?', 'Что такое кредитный комитет?'] });

  useEffect(() => {
    if (!app?.scoring) return;
    const rec = app.scoring.recommendation;
    setProduct(app.product);
    setTerm(rec.termMonths ?? app.termMonths);
    setAmount(rec.amount ?? app.amount);
    const def: Outcome = rec.amount && rec.amount < app.amount ? 'COUNTER_OFFER' : rec.outcome === 'DECLINE' ? 'DECLINE' : 'APPROVE';
    setOutcome(def);
    setReasons(def === 'APPROVE' ? [] : rec.reasonCodes.filter((r) => REASON_CATALOG[r]));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [app?.scoring?.id]);

  const escalate = useAction(async () => {
    await api.escalateToCommittee(session!, id!);
    toast('Заявка передана на кредитный комитет');
  });
  const submit = useAction(async (key) => {
    await api.makeDecision(
      session!,
      id!,
      {
        outcome,
        amount: outcome === 'APPROVE' ? app!.amount : amount ?? undefined,
        termMonths: outcome === 'APPROVE' ? app!.termMonths : term,
        product: outcome === 'APPROVE' ? app!.product : product,
        reasons,
        clientText: text,
        internalComment: comment,
        doc: outcome === 'REQUEST_DOCS' ? { type: doc.type, title: doc.title, why: doc.why, deadline: new Date(Date.now() + doc.deadline * 86400_000).toISOString(), comment: doc.comment } : undefined,
        aiTextChecked: checked,
      },
      key,
    );
    toast('Решение отправлено клиенту');
    nav(`/bank/applications/${id}`);
  });

  if (q.error) return <ErrorState error={q.error} onRetry={() => q.reload()} />;
  if (!app) return <Loading lines={6} />;
  if (user!.role !== 'underwriter') return <Navigate to={`/bank/applications/${app.id}`} replace />;
  const sc = app.scoring;

  const p = productByCode(outcome === 'APPROVE' ? app.product : product);
  const a = outcome === 'APPROVE' ? app.amount : amount ?? 0;
  const t = outcome === 'APPROVE' ? app.termMonths : term;
  const pay = sc ? monthlyLoad(p.code, a, t) : 0;
  const dscr = sc ? sc.cashFlow / (sc.currentPayments + pay) : 0;
  const rest = sc ? sc.cashFlow - sc.currentPayments - pay : 0;
  const isOffer = outcome === 'APPROVE' || outcome === 'COUNTER_OFFER';
  const errs: string[] = [];
  if (isOffer) {
    if (a < p.amountMin || a > p.amountMax) errs.push(`Сумма вне диапазона продукта (${money(p.amountMin)} – ${money(p.amountMax)})`);
    if (t < p.termMin || t > p.termMax) errs.push(`Срок вне диапазона продукта (${p.termMin}–${p.termMax} мес)`);
    if (dscr < 1.3) errs.push(`DSCR ${dec2(dscr)} — ниже 1,3: клиенту не хватит денег на платёж`);
  }
  if (outcome === 'DECLINE' && !reasons.length) errs.push('Для отказа выберите хотя бы одну причину');
  if (outcome === 'COUNTER_OFFER' && !reasons.length) errs.push('Укажите, почему условия другие');
  if (outcome === 'REQUEST_DOCS' && (!doc.title.trim() || !doc.why.trim())) errs.push('Для запроса заполните: что нужно, зачем, срок');
  if (!text.trim()) errs.push('Нужен текст для клиента');
  if (text.trim() && !checked) errs.push('Отметьте, что проверили текст для клиента');
  const overLimit = isOffer && a > (user!.authorityLimit ?? 0) && !app.committee;
  const blocked = !app.permissions.decide ? 'Решение недоступно: проверьте статус заявки, комплаенс и данные источников. Повторное решение без нового раунда рассмотрения запрещено.' : app.assignee?.userId !== user!.id ? 'Сначала возьмите заявку в работу' : null;

  const draft = async () => {
    setAiErr(null);
    setAiBusy(true);
    try {
      const tx = await api.draftClientText(session!, app.id, outcome, reasons, isOffer ? a : undefined);
      setText(tx);
      setChecked(false);
    } catch (e) {
      setAiErr((e as Error).message);
    } finally {
      setAiBusy(false);
    }
  };

  return (
    <>
      <PageTitle crumbs={`Заявка ${app.number} › Решение`} title={`Решение по заявке ${app.number}`} right={<span className="small muted">{COMPANY_SHORT[app.companyId]} · запрос {money(app.amount)} на {app.termMonths} мес</span>} />
      {blocked && <div className="warn-box">{blocked}</div>}
      <div className="row">
        <div className="grow stack">
          <section className="card">
            <h2 className="h2">Исход</h2>
            <RadioGroup
              name="outcome"
              row
              value={outcome}
              onChange={(v) => {
                setOutcome(v);
                setChecked(false);
              }}
              options={[
                { value: 'APPROVE', label: 'Одобрить как есть' },
                { value: 'COUNTER_OFFER', label: 'Встречное предложение' },
                { value: 'REQUEST_DOCS', label: 'Запросить документы' },
                { value: 'DECLINE', label: 'Отказать' },
              ]}
            />
            {sc && (
              <div className="info-box">
                Рекомендация правил: <b>{sc.recommendation.outcome}</b>
                {sc.recommendation.amount ? ` · ${money(sc.recommendation.amount)} на ${sc.recommendation.termMonths} мес, DSCR ${dec2(sc.recommendation.dscrAtAmount ?? 0)}` : ''}. Решение — ваше; риск-балл не редактируется.
              </div>
            )}
          </section>

          {isOffer && (
            <section className="card">
              <h2 className="h2">Условия</h2>
              {outcome === 'COUNTER_OFFER' ? (
                <div className="grid-fields">
                  <SelectField label="Продукт" value={product} onChange={(v) => { setProduct(v); const ts = termOptions(v); if (!ts.includes(term)) setTerm(ts[0]); }} options={PRODUCTS.map((x) => ({ value: x.code, label: x.name }))} />
                  <MoneyField label="Сумма" value={amount} onChange={setAmount} hint={`${money(p.amountMin)} – ${money(p.amountMax)}`} />
                  <SelectField label="Срок" value={term} onChange={setTerm} options={Array.from({ length: p.termMax - p.termMin + 1 }, (_, i) => p.termMin + i).map((x) => ({ value: x, label: `${x} мес` }))} />
                </div>
              ) : (
                <div className="small">
                  {PRODUCT_NAME[app.product]} · {money(app.amount)} · {app.termMonths} мес — как запросил клиент
                </div>
              )}
              {sc && (
                <div className="grid-3" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(min(180px, 100%), 1fr))', gap: 12 }}>
                  <div className="panel">
                    <span className="xs muted">{p.kind === 'limit' ? 'Проценты при 50% лимита' : 'Платёж'}</span>
                    <b className="h3">{money(pay)}</b>
                  </div>
                  <div className="panel">
                    <span className="xs muted">DSCR</span>
                    <b className="h3" style={{ color: dscr < 1.3 ? 'var(--c-negative-ink)' : 'var(--c-positive)' }}>
                      {dec2(dscr)}
                    </b>
                  </div>
                  <div className="panel">
                    <span className="xs muted">Остаток потока</span>
                    <b className="h3">{money(rest)}</b>
                  </div>
                </div>
              )}
              {overLimit && (
                <div className="warn-box row-c between">
                  <span>
                    Сумма {money(a)} выше вашего лимита полномочий ({money(user!.authorityLimit ?? 0)}). Нужна эскалация на кредитный комитет.
                  </span>
                  <Btn view="primary" size={40} onClick={() => escalate.run()} loading={escalate.pending}>
                    Передать на кредитный комитет
                  </Btn>
                </div>
              )}
              {app.committee && <div className="info-box">Заявка на кредитном комитете. Решение будет записано от имени комитета.</div>}
            </section>
          )}

          {outcome === 'REQUEST_DOCS' && (
            <section className="card">
              <h2 className="h2">Что запросить</h2>
              <div className="grid-fields">
                <TextField label="Что нужно" value={doc.title} onChange={(v) => setDoc({ ...doc, title: v })} />
                <SelectField label="Срок" value={doc.deadline} onChange={(v) => setDoc({ ...doc, deadline: v })} options={[1, 3, 5, 7].map((d) => ({ value: d, label: `${d} дн.` }))} />
              </div>
              <TextField label="Зачем (увидит клиент)" value={doc.why} onChange={(v) => setDoc({ ...doc, why: v })} />
              <TextField label="Комментарий клиенту" value={doc.comment} onChange={(v) => setDoc({ ...doc, comment: v })} />
            </section>
          )}

          <section className="card">
            <h2 className="h2">Причины</h2>
            <span className="small muted">Выбирайте только допустимые причины из справочника — по ним ИИ подготовит текст для клиента.</span>
            <div className="row-c">
              {REASON_KEYS.map((k) => (
                <button
                  key={k}
                  type="button"
                  className="chip"
                  aria-pressed={reasons.includes(k)}
                  onClick={() => setReasons((r) => (r.includes(k) ? r.filter((x) => x !== k) : [...r, k]))}
                  style={{ border: 0, cursor: 'pointer', padding: '8px 10px', background: reasons.includes(k) ? 'var(--c-black)' : 'var(--c-bg)', color: reasons.includes(k) ? '#fff' : 'var(--c-text)' }}
                  title={REASON_CATALOG[k].plain}
                >
                  {REASON_CATALOG[k].bank.split(' — ')[0]}
                </button>
              ))}
            </div>
          </section>

          <section className="card">
            <div className="row-c between">
              <h2 className="h2">Текст для клиента</h2>
              <Btn view="secondary" size={40} onClick={draft} loading={aiBusy}>
                <span className="row-c" style={{ gap: 8 }}>
                  <Px name="gem" size={14} color="var(--c-ai)" /> Черновик от ИИ
                </span>
              </Btn>
            </div>
            {aiErr && <ErrorState error={aiErr} />}
            <textarea className="native" value={text} onChange={(e) => { setText(e.target.value); setChecked(false); }} placeholder="Простыми словами: что решил банк и почему" style={{ minHeight: 120 }} />
            <span className="xs muted">ИИ пишет только по выбранным причинам. Исход и условия он не меняет — это решение сотрудника.</span>
            <Check checked={checked} onChange={setChecked} label="Я проверил текст: он соответствует решению и причинам" />
            <label className="field">
              <span className="lbl">Внутренний комментарий (клиент не видит)</span>
              <textarea className="native" value={comment} onChange={(e) => setComment(e.target.value)} />
            </label>
          </section>
        </div>

        <aside className="side stack">
          <section className="card tight" style={{ boxShadow: 'inset 0 0 0 2px var(--c-line)' }}>
            <span className="caps muted">Так увидит клиент</span>
            <Chip kind={outcome === 'APPROVE' ? 'high' : outcome === 'DECLINE' ? 'low' : outcome === 'REQUEST_DOCS' ? 'attention' : 'mid'}>{outcome === 'APPROVE' ? 'Одобрено' : outcome === 'COUNTER_OFFER' ? 'Банк предлагает другие условия' : outcome === 'REQUEST_DOCS' ? 'Нужен документ' : 'Не одобрено'}</Chip>
            <b className="h3">{outcome === 'APPROVE' ? `Одобрено: ${money(app.amount)}` : outcome === 'COUNTER_OFFER' ? `Можем дать ${money(a)} вместо ${money(app.amount)}` : outcome === 'REQUEST_DOCS' ? doc.title : 'Банк не может выдать кредит по текущим данным'}</b>
            <span className="small">{text || <span className="muted">Текст появится здесь</span>}</span>
            {reasons.length > 0 && outcome !== 'APPROVE' && (
              <ul className="small" style={{ margin: 0, paddingLeft: 18 }}>
                {reasons.map((r) => (
                  <li key={r}>{REASON_CATALOG[r].plain}</li>
                ))}
              </ul>
            )}
          </section>
          <section className="card tight">
            {errs.length > 0 && (
              <ul className="small" style={{ margin: 0, paddingLeft: 18, color: 'var(--c-negative-ink)' }}>
                {errs.map((e) => (
                  <li key={e}>{e}</li>
                ))}
              </ul>
            )}
            <Btn view="accent" block onClick={() => submit.run()} loading={submit.pending} disabled={!!blocked || errs.length > 0 || overLimit}>
              Отправить клиенту
            </Btn>
            {submit.error && <ErrorState error={submit.error} />}
            <span className="xs muted">Решение уйдёт клиенту сразу. Повторное решение — только после нового раунда рассмотрения.</span>
          </section>
        </aside>
      </div>
    </>
  );
}
