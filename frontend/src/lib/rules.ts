import type { Company, Financials, LegalForm, Product, Purpose, Segment } from '../api';
import { money } from './format';
import { LEGAL_FORM_NAME, PURPOSE_NAME, SEGMENT_NAME } from './labels';

// Те же правила каталога, что на бэкенде (backend/services/products.py). Нужны, чтобы ещё
// до отправки показать, какие продукты подходят, и посчитать платёж. Решение всё равно
// принимает бэкенд — здесь только подсказки.

export const MICRO_MAX_EMPLOYEES = 15;
export const MICRO_MAX_REVENUE_RUB = 120_000_000;

/** Сегмент по 209-ФЗ: микро — до 15 сотрудников и до 120 млн ₽ выручки в год */
export function deriveSegment(employees: number, annualRevenue: number): Segment {
  return employees <= MICRO_MAX_EMPLOYEES && annualRevenue <= MICRO_MAX_REVENUE_RUB ? 'micro' : 'small';
}

/** Полных месяцев с даты регистрации */
export function companyAgeMonths(registrationDate: string, now = new Date()): number {
  const reg = new Date(registrationDate);
  let months = (now.getUTCFullYear() - reg.getUTCFullYear()) * 12 + (now.getUTCMonth() - reg.getUTCMonth());
  if (now.getUTCDate() < reg.getUTCDate()) months -= 1;
  return Math.max(months, 0);
}

export interface Applicant {
  segment: Segment;
  purpose: Purpose;
  amount: number;
  term: number;
  legalForm: LegalForm;
  ageMonths: number;
}

export function applicantFrom(company: Company, financials: Financials, purpose: Purpose, amount: number, term: number): Applicant {
  return {
    segment: deriveSegment(company.employee_count, financials.annual_revenue_rub),
    purpose,
    amount,
    term,
    legalForm: company.legal_form,
    ageMonths: companyAgeMonths(company.registration_date),
  };
}

const extras = (p: Product) => p.extras as { legal_forms?: LegalForm[]; min_company_age_months?: number };

/** Почему продукт не подходит. Пустой список — подходит */
export function mismatchReasons(p: Product, a: Applicant): string[] {
  const reasons: string[] = [];
  if (p.segment !== 'both' && p.segment !== a.segment) reasons.push(`только для сегмента «${SEGMENT_NAME[p.segment].toLowerCase()}»`);
  if (!p.purposes.includes(a.purpose)) reasons.push(`не для цели «${PURPOSE_NAME[a.purpose].toLowerCase()}»`);
  if (a.amount < p.min_amount_rub || a.amount > p.max_amount_rub) reasons.push(`сумма от ${money(p.min_amount_rub)} до ${money(p.max_amount_rub)}`);
  if (a.term < p.min_term_months || a.term > p.max_term_months) reasons.push(`срок от ${p.min_term_months} до ${p.max_term_months} мес.`);
  const forms = extras(p).legal_forms;
  if (forms?.length && !forms.includes(a.legalForm)) reasons.push(`только для: ${forms.map((f) => LEGAL_FORM_NAME[f]).join(', ')}`);
  const minAge = extras(p).min_company_age_months;
  if (minAge && a.ageMonths < minAge) reasons.push(`компания работает от ${minAge} мес.`);
  return reasons;
}

/** Какой продукт подберёт банк: из подходящих — с самой низкой ставкой */
export function pickProduct(products: Product[], a: Applicant): Product | null {
  const fitting = products.filter((p) => mismatchReasons(p, a).length === 0);
  if (!fitting.length) return null;
  return fitting.reduce((best, p) => (p.rate_min_percent < best.rate_min_percent || (p.rate_min_percent === best.rate_min_percent && p.display_order < best.display_order) ? p : best));
}

/** Ежемесячный аннуитетный платёж, ₽ */
export function annuityPayment(amount: number, ratePercent: number, term: number): number {
  if (term <= 0) return amount;
  const r = ratePercent / 100 / 12;
  if (r === 0) return Math.round(amount / term);
  return Math.round((amount * r) / (1 - (1 + r) ** -term));
}

export interface PaymentCalc {
  payment: number;
  total: number;
  overpayment: number;
}

export function calcPayment(amount: number, ratePercent: number, term: number): PaymentCalc {
  const payment = annuityPayment(amount, ratePercent, term);
  const total = payment * term;
  return { payment, total, overpayment: total - amount };
}

/**
 * Сколько денег остаётся в месяц после всех платежей: выручка − расходы − текущие платежи по долгам − новый платёж.
 * Ориентир «запаса прочности» — по данным профиля на момент заявки.
 */
export function monthlyCushion(monthlyRevenue: number, monthlyExpenses: number, currentDebtPayments: number, newPayment: number): number {
  return monthlyRevenue - monthlyExpenses - currentDebtPayments - newPayment;
}
