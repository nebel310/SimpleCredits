import { useState } from 'react';
import type { Application, Product } from '../../api';
import { date, money, months, monthsUpTo, rate } from '../../lib/format';
import { calcPayment, monthlyCushion } from '../../lib/rules';
import { Btn, MoneyField, TextField } from '../../ui/kit';

/** Условия предложения банка: продукт, сумма, ставка, платёж, а после выдачи — договор */
export function OfferCard({ a }: { a: Application }) {
  const o = a.offer!;
  const changed = o.amount_rub !== a.application.requested_amount_rub;
  return (
    <section className="card" aria-label="Условия предложения">
      <div className="row-c between">
        <h2 className="h2">{a.status === 'issued' ? 'Кредит' : 'Условия предложения'}</h2>
        {a.status === 'issued' && <span className="small muted">выдан {date(a.issued_at ?? undefined)}</span>}
      </div>
      <dl className="dl-grid">
        {a.status === 'issued' && (
          <div>
            <dt>Договор</dt>
            <dd>№ {a.contract_number}</dd>
          </div>
        )}
        <div>
          <dt>Продукт</dt>
          <dd>{o.product_name}</dd>
        </div>
        <div>
          <dt>Сумма</dt>
          <dd>
            {money(o.amount_rub)}
            {changed && <span className="xs muted"> вместо {money(a.application.requested_amount_rub)}</span>}
          </dd>
        </div>
        <div>
          <dt>Срок</dt>
          <dd>{months(o.term_months)}</dd>
        </div>
        <div>
          <dt>Ставка</dt>
          <dd>{rate(o.rate_percent)} годовых</dd>
        </div>
        <div>
          <dt>Платёж в месяц</dt>
          <dd>{money(o.monthly_payment_rub)}</dd>
        </div>
        <div>
          <dt>Всего выплатить</dt>
          <dd>{money(o.total_payment_rub)}</dd>
        </div>
        <div>
          <dt>Переплата</dt>
          <dd>{money(o.overpayment_rub)}</dd>
        </div>
      </dl>
      <span className="xs muted">Платёж аннуитетный — одинаковый каждый месяц. Ставка зависит от оценки риска и лежит в диапазоне продукта.</span>
      {a.status === 'issued' && <div className="info-box">Выдача модельная: номер договора и перевод синтетические, реальных денег и документов нет.</div>}
    </section>
  );
}

/**
 * «Что если?» — пересчёт платежа при другой сумме и сроке по ставке предложения и запас денег после платежей.
 * Детерминированный калькулятор на фронте: условия банка не меняет.
 */
export function WhatIf({ a, product }: { a: Application; product?: Product }) {
  const o = a.offer!;
  const [amount, setAmount] = useState<number | null>(o.amount_rub);
  const [term, setTerm] = useState<number | null>(o.term_months);
  const lim = product
    ? { aMin: product.min_amount_rub, aMax: Math.min(product.max_amount_rub, o.amount_rub), tMin: product.min_term_months, tMax: product.max_term_months }
    : { aMin: 1, aMax: o.amount_rub, tMin: 1, tMax: o.term_months };
  const err = {
    amount: amount === null || amount < lim.aMin || amount > lim.aMax ? `От ${money(lim.aMin)} до ${money(lim.aMax)}` : null,
    term: term === null || term < lim.tMin || term > lim.tMax ? `От ${lim.tMin} до ${monthsUpTo(lim.tMax)}` : null,
  };
  const ok = !err.amount && !err.term;
  const c = ok ? calcPayment(amount!, o.rate_percent, term!) : null;
  const f = a.financials;
  const cushion = c ? monthlyCushion(f.monthly_revenue_rub, f.monthly_expenses_rub, a.credit_history.monthly_debt_payments_rub, c.payment) : null;

  return (
    <section className="card" aria-label="Что если">
      <div className="stack-s">
        <h2 className="h2">Что если?</h2>
        <span className="small muted">
          Посчитайте платёж, если взять меньше или на другой срок. Ставка — как в предложении, {rate(o.rate_percent)} годовых.
        </span>
      </div>
      <div className="grid-fields">
        <MoneyField label="Сумма" value={amount} onChange={setAmount} error={err.amount} hint={`Не больше суммы предложения — ${money(lim.aMax)}`} />
        <TextField label="Срок, месяцев" value={term === null ? '' : String(term)} inputMode="numeric" onChange={(v) => setTerm(v.replace(/\D/g, '') ? Number(v.replace(/\D/g, '').slice(0, 3)) : null)} error={err.term} hint={`От ${lim.tMin} до ${lim.tMax}`} />
      </div>
      {c && cushion !== null && (
        <div className="kpis">
          <div className="kpi">
            <span className="muted small">Платёж в месяц</span>
            <b className="num" style={{ fontSize: 28 }}>
              {money(c.payment)}
            </b>
          </div>
          <div className="kpi">
            <span className="muted small">Всего выплатить</span>
            <b className="num" style={{ fontSize: 28 }}>
              {money(c.total)}
            </b>
            <span className="xs muted">переплата {money(c.overpayment)}</span>
          </div>
          <div className="kpi">
            <span className="muted small">Остаётся в месяц</span>
            <b className="num" style={{ fontSize: 28, color: cushion < 0 ? 'var(--c-negative-ink)' : undefined }}>
              {money(cushion)}
            </b>
            <span className="xs muted">{cushion < 0 ? 'платежи больше свободных денег' : 'после всех платежей'}</span>
          </div>
        </div>
      )}
      <span className="xs muted">
        Остаток = выручка в месяц − расходы в месяц − текущие платежи по кредитам − новый платёж, по данным заявки ({money(f.monthly_revenue_rub)} − {money(f.monthly_expenses_rub)} − {money(a.credit_history.monthly_debt_payments_rub)}).
      </span>
      <div className="warn-box">Предварительный расчёт. Условия банка не меняются.</div>
      {(amount !== o.amount_rub || term !== o.term_months) && (
        <div>
          <Btn
            view="outlined"
            size={40}
            onClick={() => {
              setAmount(o.amount_rub);
              setTerm(o.term_months);
            }}
          >
            Вернуть условия предложения
          </Btn>
        </div>
      )}
    </section>
  );
}
