import { describe, expect, it } from 'vitest';
import type { Product } from '../api';
import { annuityPayment, calcPayment, companyAgeMonths, deriveSegment, mismatchReasons, monthlyCushion, pickProduct, type Applicant } from './rules';

// Каталог как в backend/repositories/products.py (SEED_VERSION=2)
const P = (o: Partial<Product>): Product => ({ id: 1, code: '', name: '', description: '', product_type: 'term_loan', segment: 'both', min_amount_rub: 0, max_amount_rub: 0, min_term_months: 0, max_term_months: 0, rate_min_percent: 0, rate_max_percent: 0, purposes: [], features: [], requirements: [], extras: {}, display_order: 0, ...o });
const CATALOG: Product[] = [
  P({ code: 'microloan', name: 'Микрозайм', product_type: 'microloan', segment: 'micro', min_amount_rub: 50_000, max_amount_rub: 3_000_000, min_term_months: 1, max_term_months: 24, rate_min_percent: 22, rate_max_percent: 32, purposes: ['working_capital', 'equipment', 'other'], extras: { legal_forms: ['individual_entrepreneur', 'llc'], min_company_age_months: 6 }, display_order: 1 }),
  P({ code: 'working_capital', name: 'Оборотный кредит', product_type: 'term_loan', min_amount_rub: 100_000, max_amount_rub: 30_000_000, min_term_months: 3, max_term_months: 36, rate_min_percent: 18, rate_max_percent: 25, purposes: ['working_capital', 'expansion', 'refinancing', 'other'], extras: { min_company_age_months: 12 }, display_order: 2 }),
  P({ code: 'overdraft', name: 'Овердрафт', product_type: 'overdraft', min_amount_rub: 500_000, max_amount_rub: 15_000_000, min_term_months: 6, max_term_months: 12, rate_min_percent: 19, rate_max_percent: 26, purposes: ['working_capital'], extras: { min_company_age_months: 6 }, display_order: 3 }),
  P({ code: 'credit_line', name: 'Кредитная линия', product_type: 'credit_line', segment: 'small', min_amount_rub: 1_000_000, max_amount_rub: 50_000_000, min_term_months: 12, max_term_months: 36, rate_min_percent: 17.5, rate_max_percent: 24, purposes: ['working_capital', 'expansion', 'equipment'], extras: { legal_forms: ['llc', 'joint_stock_company'], min_company_age_months: 24 }, display_order: 4 }),
  P({ code: 'leasing', name: 'Лизинг оборудования', product_type: 'leasing', min_amount_rub: 500_000, max_amount_rub: 40_000_000, min_term_months: 12, max_term_months: 60, rate_min_percent: 17, rate_max_percent: 23, purposes: ['equipment', 'expansion'], extras: { min_company_age_months: 12 }, display_order: 5 }),
];
const by = (code: string) => CATALOG.find((p) => p.code === code)!;
const A = (o: Partial<Applicant>): Applicant => ({ segment: 'micro', purpose: 'working_capital', amount: 1_000_000, term: 12, legalForm: 'individual_entrepreneur', ageMonths: 36, ...o });

describe('сегмент по 209-ФЗ', () => {
  it('до 15 сотрудников и до 120 млн — микро', () => expect(deriveSegment(15, 120_000_000)).toBe('micro'));
  it('16 сотрудников — малый', () => expect(deriveSegment(16, 10_000_000)).toBe('small'));
  it('выручка больше 120 млн — малый', () => expect(deriveSegment(5, 120_000_001)).toBe('small'));
});

describe('возраст компании', () => {
  it('полных месяцев', () => expect(companyAgeMonths('2024-10-26T00:00:00Z', new Date('2026-10-26T00:00:00Z'))).toBe(24));
  it('день ещё не наступил — месяц не полный', () => expect(companyAgeMonths('2024-10-27T00:00:00Z', new Date('2026-10-26T00:00:00Z'))).toBe(23));
});

describe('подходит ли продукт', () => {
  it('всё совпадает — причин нет', () => expect(mismatchReasons(by('working_capital'), A({}))).toEqual([]));
  it('кредитная линия не для ИП и микро', () => {
    const r = mismatchReasons(by('credit_line'), A({}));
    expect(r.join(' ')).toContain('сегмента');
    expect(r.join(' ')).toContain('ООО');
  });
  it('молодая компания не проходит по возрасту', () => expect(mismatchReasons(by('leasing'), A({ purpose: 'equipment', ageMonths: 6 }))).toEqual(['компания работает от 12 мес.']));
  it('сумма вне границ', () => expect(mismatchReasons(by('microloan'), A({ amount: 5_000_000 }))[0]).toContain('сумма от'));
});

describe('подбор продукта — как на бэкенде: из подходящих самый дешёвый', () => {
  it('ИП, оборудование 500 тыс — лизинг дешевле микрозайма', () => expect(pickProduct(CATALOG, A({ purpose: 'equipment', amount: 500_000 }))?.code).toBe('leasing'));
  it('ИП, оборудование 300 тыс — лизинг не подходит по сумме, микрозайм', () => expect(pickProduct(CATALOG, A({ purpose: 'equipment', amount: 300_000 }))?.code).toBe('microloan'));
  it('ничего не подходит — null', () => expect(pickProduct(CATALOG, A({ purpose: 'refinancing', amount: 60_000_000 }))).toBeNull());
});

describe('платёж', () => {
  it('аннуитет совпадает с бэкендом: 15 млн, 20,8%, 24 мес', () => expect(annuityPayment(15_000_000, 20.8, 24)).toBe(769_312));
  it('нулевая ставка — сумма поровну', () => expect(annuityPayment(1_200_000, 0, 12)).toBe(100_000));
  it('общая сумма и переплата', () => {
    const c = calcPayment(1_000_000, 18, 12);
    expect(c.total).toBe(c.payment * 12);
    expect(c.overpayment).toBe(c.total - 1_000_000);
  });
  it('запас после платежей', () => expect(monthlyCushion(4_000_000, 3_300_000, 65_000, 275_000)).toBe(360_000));
});
