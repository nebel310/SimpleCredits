import { useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { api, useSession, type CreditHistory, type Financials, type Fns, type LegalForm, type User } from '../../api';
import { useAction } from '../../lib/hooks';
import { date, money } from '../../lib/format';
import { LEGAL_FORM_NAME } from '../../lib/labels';
import { Btn, Check, DateField, ErrorState, MoneyField, PageTitle, SelectField, TextField, toast } from '../../ui/kit';

// Профиль компании (USERFLOW, шаг 3): реквизиты, финансы и кредитная история.
// Заполняется один раз через PATCH /auth/me и дальше подставляется во все заявки.

type Money = number | null;
const toDay = (iso?: string | null) => (iso ? iso.slice(0, 10) : '');
const fromDay = (d: string) => `${d}T00:00:00Z`;
const digits = (v: string, max: number) => v.replace(/\D/g, '').slice(0, max);
const today = () => new Date().toISOString().slice(0, 10);
/** Дата обязательна и не позже сегодняшней */
const dateError = (d: string, what: string) => (!d ? 'Укажите дату' : d > today() ? `${what} не может быть в будущем` : d < '1991-01-01' ? 'Проверьте год' : null);

function IntField({ label, value, onChange, error, hint }: { label: string; value: number | null; onChange: (v: number | null) => void; error?: string | null; hint?: string }) {
  return <TextField label={label} value={value === null ? '' : String(value)} inputMode="numeric" onChange={(v) => onChange(v.replace(/\D/g, '') ? Number(digits(v, 9)) : null)} error={error} hint={hint} />;
}

function initial(u: User | null) {
  const c = u?.company;
  const f = u?.financials;
  const h = u?.credit_history;
  return {
    inn: c?.inn ?? '',
    ogrn: c?.ogrn ?? '',
    legal_name: c?.legal_name ?? '',
    legal_form: (c?.legal_form ?? 'llc') as LegalForm,
    okved: c?.okved ?? '',
    region: c?.region ?? '',
    registration_date: toDay(c?.registration_date),
    employee_count: c?.employee_count ?? null,
    fin: {
      annual_revenue_rub: f?.annual_revenue_rub ?? null,
      annual_net_profit_rub: f?.annual_net_profit_rub ?? null,
      ebitda_rub: f?.ebitda_rub ?? null,
      total_debt_rub: f?.total_debt_rub ?? null,
      monthly_revenue_rub: f?.monthly_revenue_rub ?? null,
      monthly_expenses_rub: f?.monthly_expenses_rub ?? null,
      accounts_receivable_rub: f?.accounts_receivable_rub ?? null,
      cash_balance_rub: f?.cash_balance_rub ?? null,
    } as Record<Exclude<keyof Financials, 'period_end'>, Money>,
    period_end: toDay(f?.period_end),
    ch: {
      active_obligations_count: h?.active_obligations_count ?? null,
      total_outstanding_rub: h?.total_outstanding_rub ?? null,
      monthly_debt_payments_rub: h?.monthly_debt_payments_rub ?? null,
      max_days_past_due_12m: h?.max_days_past_due_12m ?? null,
      closed_obligations_count: h?.closed_obligations_count ?? null,
      applications_last_6m: h?.applications_last_6m ?? null,
    } as Record<Exclude<keyof CreditHistory, 'has_current_past_due' | 'credit_utilization'>, Money>,
    has_current_past_due: h?.has_current_past_due ?? false,
    utilization: h ? Math.round(h.credit_utilization * 100) : null,
  };
}

const FIN_FIELDS: { key: keyof ReturnType<typeof initial>['fin']; label: string; signed?: boolean }[] = [
  { key: 'annual_revenue_rub', label: 'Выручка за год' },
  { key: 'annual_net_profit_rub', label: 'Чистая прибыль за год', signed: true },
  { key: 'ebitda_rub', label: 'EBITDA за год', signed: true },
  { key: 'total_debt_rub', label: 'Общий долг' },
  { key: 'monthly_revenue_rub', label: 'Выручка в месяц' },
  { key: 'monthly_expenses_rub', label: 'Расходы в месяц' },
  { key: 'accounts_receivable_rub', label: 'Дебиторская задолженность' },
  { key: 'cash_balance_rub', label: 'Деньги на счетах' },
];

export function Profile() {
  const { user, setUser } = useSession();
  const nav = useNavigate();
  const [params] = useSearchParams();
  const [v, setV] = useState(() => initial(user));
  const [tried, setTried] = useState(false);
  const [fns, setFns] = useState<Fns | null>(null);
  const set = <K extends keyof typeof v>(k: K, val: (typeof v)[K]) => setV((s) => ({ ...s, [k]: val }));

  const innOk = /^\d{10}$|^\d{12}$/.test(v.inn);

  const egrul = useAction(async () => {
    const [e, f] = await Promise.all([api.egrul(v.inn), api.fns(v.inn).catch(() => null)]);
    setV((s) => ({ ...s, ogrn: e.ogrn, legal_name: e.legal_name, legal_form: e.legal_form, okved: e.okved, region: e.region, registration_date: toDay(e.registration_date), employee_count: e.employee_count }));
    setFns(f);
    toast('Реквизиты подставлены из ЕГРЮЛ');
  });
  const bki = useAction(async () => {
    const b = await api.bki(v.inn);
    setV((s) => ({
      ...s,
      ch: {
        active_obligations_count: b.active_obligations_count,
        total_outstanding_rub: b.total_outstanding_rub,
        monthly_debt_payments_rub: b.monthly_debt_payments_rub,
        max_days_past_due_12m: b.max_days_past_due_12m,
        closed_obligations_count: b.closed_obligations_count,
        applications_last_6m: b.applications_last_6m,
      },
      has_current_past_due: b.has_current_past_due,
      utilization: Math.round(b.credit_utilization * 100),
    }));
    toast(`Кредитная история из БКИ на ${date(b.last_update)}`);
  });

  const err = {
    inn: !innOk ? 'ИНН — 10 цифр для ООО или 12 для ИП' : null,
    ogrn: !/^\d{13,15}$/.test(v.ogrn) ? 'ОГРН — 13 цифр, ОГРНИП — 15' : null,
    legal_name: !v.legal_name.trim() ? 'Укажите название' : null,
    okved: !v.okved.trim() ? 'Укажите код ОКВЭД' : null,
    region: !v.region.trim() ? 'Укажите регион' : null,
    registration_date: dateError(v.registration_date, 'Дата регистрации'),
    employee_count: v.employee_count === null ? 'Укажите число' : null,
    period_end: dateError(v.period_end, 'Отчётный период'),
    utilization: v.utilization === null || v.utilization > 100 ? 'От 0 до 100%' : null,
  };
  const finMissing = FIN_FIELDS.filter((f) => v.fin[f.key] === null).map((f) => f.key);
  const chMissing = (Object.keys(v.ch) as (keyof typeof v.ch)[]).filter((k) => v.ch[k] === null);
  const valid = !Object.values(err).some(Boolean) && finMissing.length === 0 && chMissing.length === 0;

  const save = useAction(async () => {
    const me = await api.updateMe({
      company: { inn: v.inn, ogrn: v.ogrn, legal_name: v.legal_name.trim(), legal_form: v.legal_form, okved: v.okved.trim(), region: v.region.trim(), registration_date: fromDay(v.registration_date), employee_count: v.employee_count! },
      financials: { ...(v.fin as Record<string, number>), period_end: fromDay(v.period_end) } as unknown as Financials,
      credit_history: { ...(v.ch as Record<string, number>), has_current_past_due: v.has_current_past_due, credit_utilization: (v.utilization ?? 0) / 100 } as unknown as CreditHistory,
    });
    setUser(me);
    toast('Профиль сохранён');
    if (params.get('next') === 'apply') nav('/apply');
  });

  const show = (k: keyof typeof err) => (tried ? err[k] : null);

  return (
    <>
      <PageTitle crumbs="Профиль компании" title="Компания, финансы и кредитная история" />
      <span className="muted">Данные заполняются один раз и подставляются во все заявки. В заявку уходит их снимок на момент подачи.</span>

      <section className="card big">
        <div className="row-c between">
          <h2 className="h2">Компания</h2>
          <span className="small muted">Реквизиты можно подставить из ЕГРЮЛ по ИНН</span>
        </div>
        <div className="row" style={{ alignItems: 'flex-end' }}>
          <div style={{ flex: '1 1 260px' }}>
            <TextField label="ИНН" value={v.inn} inputMode="numeric" onChange={(x) => set('inn', digits(x, 12))} error={show('inn')} />
          </div>
          <Btn view="outlined" onClick={() => egrul.run()} loading={egrul.pending} disabled={!innOk}>
            Найти в ЕГРЮЛ
          </Btn>
        </div>
        {egrul.error && <ErrorState error={egrul.error.status === 404 ? 'Компания с таким ИНН не найдена в ЕГРЮЛ' : egrul.error} />}
        {fns && (
          <div className="info-box">
            <b>ФНС:</b> режим {fns.tax_regime} · долг перед налоговой {money(fns.tax_debt_rub)} · индекс надёжности {fns.reliability_score} из 100
            {(fns.mass_address || fns.mass_director || fns.disqualified_persons) && ' · есть признаки риска (массовый адрес, директор или дисквалификация)'}
          </div>
        )}
        <div className="grid-fields">
          <TextField label="ОГРН / ОГРНИП" value={v.ogrn} inputMode="numeric" onChange={(x) => set('ogrn', digits(x, 15))} error={show('ogrn')} />
          <TextField label="Название" value={v.legal_name} onChange={(x) => set('legal_name', x)} error={show('legal_name')} />
          <SelectField label="Форма" value={v.legal_form} options={(Object.keys(LEGAL_FORM_NAME) as LegalForm[]).map((k) => ({ value: k, label: LEGAL_FORM_NAME[k] }))} onChange={(x) => set('legal_form', x)} />
          <TextField label="ОКВЭД" value={v.okved} onChange={(x) => set('okved', x)} error={show('okved')} placeholder="62.01" />
          <TextField label="Регион" value={v.region} onChange={(x) => set('region', x)} error={show('region')} />
          <DateField label="Дата регистрации" value={v.registration_date} onChange={(x) => set('registration_date', x)} error={show('registration_date')} />
          <IntField label="Сотрудников" value={v.employee_count} onChange={(x) => set('employee_count', x)} error={show('employee_count')} />
        </div>
      </section>

      <section className="card big">
        <h2 className="h2">Финансы за последний период</h2>
        <div className="grid-fields">
          {FIN_FIELDS.map((f) => (
            <MoneyField key={f.key} label={f.label} signed={f.signed} value={v.fin[f.key]} onChange={(x) => set('fin', { ...v.fin, [f.key]: x })} error={tried && v.fin[f.key] === null ? 'Заполните' : null} hint={f.signed ? 'Убыток — со знаком минус' : undefined} />
          ))}
          <DateField label="Отчётный период по" value={v.period_end} onChange={(x) => set('period_end', x)} error={show('period_end')} />
        </div>
      </section>

      <section className="card big">
        <div className="row-c between">
          <h2 className="h2">Кредитная история</h2>
          <Btn view="outlined" size={40} onClick={() => bki.run()} loading={bki.pending} disabled={!innOk}>
            Запросить в БКИ
          </Btn>
        </div>
        {bki.error && <ErrorState error={bki.error.status === 404 ? 'По этому ИНН в БКИ ничего не найдено' : bki.error} />}
        <div className="grid-fields">
          <IntField label="Действующих кредитов" value={v.ch.active_obligations_count} onChange={(x) => set('ch', { ...v.ch, active_obligations_count: x })} error={tried && v.ch.active_obligations_count === null ? 'Заполните' : null} />
          <MoneyField label="Остаток долга по кредитам" value={v.ch.total_outstanding_rub} onChange={(x) => set('ch', { ...v.ch, total_outstanding_rub: x })} error={tried && v.ch.total_outstanding_rub === null ? 'Заполните' : null} />
          <MoneyField label="Платежи по кредитам в месяц" value={v.ch.monthly_debt_payments_rub} onChange={(x) => set('ch', { ...v.ch, monthly_debt_payments_rub: x })} error={tried && v.ch.monthly_debt_payments_rub === null ? 'Заполните' : null} />
          <IntField label="Самая долгая просрочка за год, дней" value={v.ch.max_days_past_due_12m} onChange={(x) => set('ch', { ...v.ch, max_days_past_due_12m: x })} error={tried && v.ch.max_days_past_due_12m === null ? 'Заполните' : null} />
          <IntField label="Использование кредитных лимитов, %" value={v.utilization} onChange={(x) => set('utilization', x)} error={show('utilization')} />
          <IntField label="Закрытых кредитов" value={v.ch.closed_obligations_count} onChange={(x) => set('ch', { ...v.ch, closed_obligations_count: x })} error={tried && v.ch.closed_obligations_count === null ? 'Заполните' : null} />
          <IntField label="Заявок на кредит за 6 месяцев" value={v.ch.applications_last_6m} onChange={(x) => set('ch', { ...v.ch, applications_last_6m: x })} error={tried && v.ch.applications_last_6m === null ? 'Заполните' : null} />
        </div>
        <Check checked={v.has_current_past_due} onChange={(x) => set('has_current_past_due', x)} label="Сейчас есть просрочка по кредиту" />
      </section>

      {save.error && <ErrorState error={save.error} onRetry={() => save.run()} />}
      {tried && !valid && <div className="warn-box">Заполните отмеченные поля — без них заявку отправить нельзя.</div>}
      <div className="btn-row">
        <Btn
          view="accent"
          loading={save.pending}
          onClick={() => {
            setTried(true);
            if (valid) save.run();
          }}
        >
          Сохранить профиль
        </Btn>
        {params.get('next') === 'apply' && <span className="small muted">После сохранения вернём вас к заявке</span>}
      </div>
    </>
  );
}
