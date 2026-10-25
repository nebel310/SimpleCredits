import type { CreateApplicationInput, ProfileInput } from '../api';

// Демо-аккаунты для показа. Все данные синтетические. При первом входе аккаунт регистрируется в бэкенде
// и получает профиль компании через PATCH /auth/me. Исходы ниже — то, что возвращает ML-сервис для этих данных.

export interface DemoCompany {
  key: string;
  title: string;
  scenario: string;
  email: string;
  password: string;
  username: string;
  profile: Required<Pick<ProfileInput, 'company' | 'financials' | 'credit_history'>>;
  /** Параметры, которые подставляются в форму новой заявки */
  application: CreateApplicationInput;
}

const period = '2026-09-30T00:00:00Z';

export const DEMO_COMPANIES: DemoCompany[] = [
  {
    key: 'a',
    title: 'ИП «Компания A»',
    scenario: 'Стабильный бизнес → одобрено на запрошенных условиях',
    email: 'company-a@demo.simplecredits.ru',
    password: 'demo-a-2026',
    username: 'demo_company_a',
    profile: {
      company: { inn: '7700001053', ogrn: '318774600123456', legal_name: 'ИП Компания A', legal_form: 'individual_entrepreneur', okved: '47.11', region: 'Москва', registration_date: '2018-03-15T00:00:00Z', employee_count: 14 },
      financials: { annual_revenue_rub: 48_000_000, annual_net_profit_rub: 5_600_000, ebitda_rub: 8_100_000, total_debt_rub: 1_800_000, monthly_revenue_rub: 4_000_000, monthly_expenses_rub: 3_300_000, accounts_receivable_rub: 1_400_000, cash_balance_rub: 2_200_000, period_end: period },
      credit_history: { active_obligations_count: 1, total_outstanding_rub: 1_200_000, monthly_debt_payments_rub: 65_000, max_days_past_due_12m: 0, has_current_past_due: false, credit_utilization: 0.22, closed_obligations_count: 5, applications_last_6m: 1 },
    },
    application: { product_type: 'term_loan', requested_amount_rub: 3_000_000, term_months: 12, purpose: 'working_capital', segment: 'small' },
  },
  {
    key: 'b',
    title: 'ООО «Компания B»',
    scenario: 'Сумма больше 60% выручки → одобрено, но предложат меньшую сумму',
    email: 'company-b@demo.simplecredits.ru',
    password: 'demo-b-2026',
    username: 'demo_company_b',
    profile: {
      company: { inn: '7800001481', ogrn: '1157746123456', legal_name: 'ООО Компания B', legal_form: 'llc', okved: '46.69', region: 'Санкт-Петербург', registration_date: '2015-06-01T00:00:00Z', employee_count: 42 },
      financials: { annual_revenue_rub: 30_000_000, annual_net_profit_rub: 3_300_000, ebitda_rub: 5_200_000, total_debt_rub: 2_500_000, monthly_revenue_rub: 2_500_000, monthly_expenses_rub: 2_050_000, accounts_receivable_rub: 2_100_000, cash_balance_rub: 1_900_000, period_end: period },
      credit_history: { active_obligations_count: 2, total_outstanding_rub: 2_000_000, monthly_debt_payments_rub: 110_000, max_days_past_due_12m: 0, has_current_past_due: false, credit_utilization: 0.3, closed_obligations_count: 6, applications_last_6m: 1 },
    },
    application: { product_type: 'credit_line', requested_amount_rub: 20_000_000, term_months: 24, purpose: 'expansion', segment: 'small' },
  },
  {
    key: 'c',
    title: 'ООО «Компания C»',
    scenario: 'Высокая долговая нагрузка → пограничная зона риска, нужна проверка',
    email: 'company-c@demo.simplecredits.ru',
    password: 'demo-c-2026',
    username: 'demo_company_c',
    profile: {
      company: { inn: '7900000029', ogrn: '1197746234567', legal_name: 'ООО Компания C', legal_form: 'llc', okved: '56.10', region: 'Казань', registration_date: '2019-09-10T00:00:00Z', employee_count: 25 },
      financials: { annual_revenue_rub: 26_000_000, annual_net_profit_rub: 1_400_000, ebitda_rub: 2_600_000, total_debt_rub: 5_000_000, monthly_revenue_rub: 2_100_000, monthly_expenses_rub: 1_850_000, accounts_receivable_rub: 900_000, cash_balance_rub: 700_000, period_end: period },
      credit_history: { active_obligations_count: 4, total_outstanding_rub: 4_750_000, monthly_debt_payments_rub: 500_000, max_days_past_due_12m: 5, has_current_past_due: false, credit_utilization: 0.68, closed_obligations_count: 3, applications_last_6m: 3 },
    },
    application: { product_type: 'overdraft', requested_amount_rub: 1_500_000, term_months: 12, purpose: 'working_capital', segment: 'small' },
  },
  {
    key: 'd',
    title: 'ИП «Компания D»',
    scenario: 'Продукт не выбран → банк подберёт его сам',
    email: 'company-d@demo.simplecredits.ru',
    password: 'demo-d-2026',
    username: 'demo_company_d',
    profile: {
      company: { inn: '502345678901', ogrn: '326500100234567', legal_name: 'ИП Компания D', legal_form: 'individual_entrepreneur', okved: '62.01', region: 'Московская область', registration_date: '2026-05-12T00:00:00Z', employee_count: 2 },
      financials: { annual_revenue_rub: 2_400_000, annual_net_profit_rub: 300_000, ebitda_rub: 420_000, total_debt_rub: 0, monthly_revenue_rub: 400_000, monthly_expenses_rub: 330_000, accounts_receivable_rub: 120_000, cash_balance_rub: 250_000, period_end: period },
      credit_history: { active_obligations_count: 0, total_outstanding_rub: 0, monthly_debt_payments_rub: 0, max_days_past_due_12m: 0, has_current_past_due: false, credit_utilization: 0, closed_obligations_count: 0, applications_last_6m: 0 },
    },
    application: { product_type: null, requested_amount_rub: 500_000, term_months: 12, purpose: 'equipment', segment: 'micro' },
  },
  {
    key: 'e',
    title: 'ООО «Компания E»',
    scenario: 'Текущая просрочка по кредитам → отказ',
    email: 'company-e@demo.simplecredits.ru',
    password: 'demo-e-2026',
    username: 'demo_company_e',
    profile: {
      company: { inn: '7734567890', ogrn: '1207746345678', legal_name: 'ООО Компания E', legal_form: 'llc', okved: '41.20', region: 'Новосибирск', registration_date: '2020-02-20T00:00:00Z', employee_count: 18 },
      financials: { annual_revenue_rub: 18_000_000, annual_net_profit_rub: -600_000, ebitda_rub: 400_000, total_debt_rub: 7_500_000, monthly_revenue_rub: 1_500_000, monthly_expenses_rub: 1_560_000, accounts_receivable_rub: 2_600_000, cash_balance_rub: 150_000, period_end: period },
      credit_history: { active_obligations_count: 3, total_outstanding_rub: 6_900_000, monthly_debt_payments_rub: 420_000, max_days_past_due_12m: 96, has_current_past_due: true, credit_utilization: 0.91, closed_obligations_count: 2, applications_last_6m: 5 },
    },
    application: { product_type: 'term_loan', requested_amount_rub: 4_000_000, term_months: 24, purpose: 'refinancing', segment: 'small' },
  },
];

/** Администратор создаётся бэкендом при старте из ADMIN_EMAIL / ADMIN_PASSWORD (.env) */
export const DEMO_ADMIN = {
  email: import.meta.env.VITE_ADMIN_EMAIL || 'admin@admin.com',
  password: import.meta.env.VITE_ADMIN_PASSWORD || 'admin',
};

export const demoByEmail = (email?: string | null) => DEMO_COMPANIES.find((d) => d.email === email);
