import { describe, expect, it } from 'vitest';
import { DEMO_COMPANIES } from './demo';
import { deriveSegment } from './rules';

// Ограничения из backend/schemas/applications.py и каталог продуктов из USERFLOW §4 (seed)
const SEED: Record<string, { min: number; max: number; tmin: number; tmax: number; purposes?: string[] }> = {
  microloan: { min: 50_000, max: 3_000_000, tmin: 1, tmax: 24 },
  term_loan: { min: 100_000, max: 30_000_000, tmin: 3, tmax: 36 },
  overdraft: { min: 500_000, max: 15_000_000, tmin: 6, tmax: 12 },
  credit_line: { min: 1_000_000, max: 50_000_000, tmin: 12, tmax: 36 },
  leasing: { min: 500_000, max: 40_000_000, tmin: 12, tmax: 60 },
};

describe.each(DEMO_COMPANIES.map((d) => [d.title, d] as const))('демо-компания %s', (_, d) => {
  const { company: c, financials: f, credit_history: h } = d.profile;

  it('реквизиты проходят валидацию бэкенда', () => {
    expect(c.inn).toMatch(/^\d{10}$|^\d{12}$/);
    expect(c.ogrn).toMatch(/^\d{13,15}$/);
    expect(c.employee_count).toBeGreaterThanOrEqual(0);
    expect(['llc', 'individual_entrepreneur', 'joint_stock_company']).toContain(c.legal_form);
    expect(Number.isNaN(Date.parse(c.registration_date))).toBe(false);
  });

  it('финансы и кредитная история в допустимых границах', () => {
    for (const k of ['annual_revenue_rub', 'total_debt_rub', 'monthly_revenue_rub', 'monthly_expenses_rub', 'accounts_receivable_rub', 'cash_balance_rub'] as const) expect(f[k]).toBeGreaterThanOrEqual(0);
    for (const k of ['active_obligations_count', 'total_outstanding_rub', 'monthly_debt_payments_rub', 'max_days_past_due_12m', 'closed_obligations_count', 'applications_last_6m'] as const) expect(h[k]).toBeGreaterThanOrEqual(0);
    expect(h.credit_utilization).toBeGreaterThanOrEqual(0);
    expect(h.credit_utilization).toBeLessThanOrEqual(1);
    expect(Number.isInteger(f.annual_revenue_rub)).toBe(true);
  });

  it('сегмент в заявке — тот, что определит банк', () => {
    expect(d.application.segment).toBe(deriveSegment(c.employee_count, f.annual_revenue_rub));
  });

  it('дата регистрации в прошлом, месячная выручка согласована с годовой', () => {
    expect(Date.parse(c.registration_date)).toBeLessThan(Date.now());
    expect(Math.abs(f.monthly_revenue_rub * 12 - f.annual_revenue_rub) / f.annual_revenue_rub).toBeLessThan(0.05);
  });

  it('форма компании соответствует ИНН: 12 цифр — ИП, 10 — организация', () => {
    expect(c.legal_form === 'individual_entrepreneur').toBe(c.inn.length === 12);
  });

  it('заявка укладывается в границы продукта', () => {
    const a = d.application;
    expect(a.requested_amount_rub).toBeGreaterThan(0);
    expect(a.term_months).toBeGreaterThanOrEqual(1);
    if (a.product_type) {
      const p = SEED[a.product_type];
      expect(a.requested_amount_rub).toBeGreaterThanOrEqual(p.min);
      expect(a.requested_amount_rub).toBeLessThanOrEqual(p.max);
      expect(a.term_months).toBeGreaterThanOrEqual(p.tmin);
      expect(a.term_months).toBeLessThanOrEqual(p.tmax);
    }
  });
});

it('у демо-аккаунтов разные email', () => {
  expect(new Set(DEMO_COMPANIES.map((d) => d.email)).size).toBe(DEMO_COMPANIES.length);
});
