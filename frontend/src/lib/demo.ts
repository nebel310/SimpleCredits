import type { CreateApplicationInput, ProfileInput } from '../api';

// Демо-аккаунты для показа. Все данные синтетические. При первом входе аккаунт регистрируется
// и получает профиль компании через PATCH /auth/me. Исходы ниже — то, что решает банк для этих данных.

export interface DemoCompany {
  key: string;
  title: string;
  scenario: string;
  email: string;
  password: string;
  username: string;
  profile: Required<Pick<ProfileInput, 'company' | 'financials' | 'credit_history'>>;
  /** Параметры, которые подставляются в форму новой заявки */
  application: Omit<CreateApplicationInput, 'consents'>;
}

const period = '2026-09-30T00:00:00Z';

/** Дата регистрации «N дней назад» — так её отдаёт мок ЕГРЮЛ, и профиль с ним совпадает */
const daysAgo = (n: number) => {
  const d = new Date(Date.now() - n * 86_400_000);
  return `${d.toISOString().slice(0, 10)}T00:00:00Z`;
};

// ИНН подобраны так, чтобы ответы мок-ЕГРЮЛ и мок-БКИ вели к нужному сценарию: реквизиты в профиле — как в ЕГРЮЛ,
// кредитная история — как в БКИ (банк берёт её оттуда). Финансы — синтетические, заполняет клиент.
export const DEMO_COMPANIES: DemoCompany[] = [
  {
    key: 'a',
    title: 'ИП Компания 9986',
    scenario: 'Стабильный бизнес → одобрено: можно принять предложение и оформить кредит',
    email: 'company-a@demo.simplecredits.ru',
    password: 'demo-a-2026',
    username: 'demo_company_a',
    profile: {
      company: { inn: '771588139986', ogrn: '308823309165255', legal_name: 'ИП Компания 9986', legal_form: 'individual_entrepreneur', okved: '43.21', region: 'Санкт-Петербург', registration_date: daysAgo(3044), employee_count: 12 },
      financials: { annual_revenue_rub: 48_000_000, annual_net_profit_rub: 5_600_000, ebitda_rub: 8_100_000, total_debt_rub: 0, monthly_revenue_rub: 4_000_000, monthly_expenses_rub: 3_300_000, accounts_receivable_rub: 1_400_000, cash_balance_rub: 2_200_000, period_end: period },
      credit_history: { active_obligations_count: 0, total_outstanding_rub: 0, monthly_debt_payments_rub: 0, max_days_past_due_12m: 0, has_current_past_due: false, credit_utilization: 0, closed_obligations_count: 7, applications_last_6m: 0 },
    },
    application: { product_type: 'term_loan', requested_amount_rub: 3_000_000, term_months: 12, purpose: 'working_capital', segment: 'micro' },
  },
  {
    key: 'b',
    title: 'ООО Компания 2785',
    scenario: 'Сумма больше 60% годовой выручки → банк предложит меньшую сумму',
    email: 'company-b@demo.simplecredits.ru',
    password: 'demo-b-2026',
    username: 'demo_company_b',
    profile: {
      company: { inn: '7748132785', ogrn: '1128819140054', legal_name: 'ООО Компания 2785', legal_form: 'llc', okved: '49.41', region: 'Санкт-Петербург', registration_date: daysAgo(2783), employee_count: 62 },
      financials: { annual_revenue_rub: 30_000_000, annual_net_profit_rub: 3_300_000, ebitda_rub: 5_200_000, total_debt_rub: 0, monthly_revenue_rub: 2_500_000, monthly_expenses_rub: 2_050_000, accounts_receivable_rub: 2_100_000, cash_balance_rub: 1_900_000, period_end: period },
      credit_history: { active_obligations_count: 0, total_outstanding_rub: 0, monthly_debt_payments_rub: 0, max_days_past_due_12m: 0, has_current_past_due: false, credit_utilization: 0, closed_obligations_count: 1, applications_last_6m: 1 },
    },
    application: { product_type: 'credit_line', requested_amount_rub: 20_000_000, term_months: 24, purpose: 'expansion', segment: 'small' },
  },
  {
    key: 'c',
    title: 'ООО Компания 7752',
    scenario: 'Риск в пограничной зоне → заявку проверит сотрудник банка',
    email: 'company-c@demo.simplecredits.ru',
    password: 'demo-c-2026',
    username: 'demo_company_c',
    profile: {
      company: { inn: '7748587752', ogrn: '1214196394805', legal_name: 'ООО Компания 7752', legal_form: 'llc', okved: '46.90', region: 'Казань', registration_date: daysAgo(1305), employee_count: 76 },
      financials: { annual_revenue_rub: 26_000_000, annual_net_profit_rub: 1_400_000, ebitda_rub: 2_600_000, total_debt_rub: 6_813_791, monthly_revenue_rub: 2_100_000, monthly_expenses_rub: 1_850_000, accounts_receivable_rub: 900_000, cash_balance_rub: 700_000, period_end: period },
      credit_history: { active_obligations_count: 2, total_outstanding_rub: 6_813_791, monthly_debt_payments_rub: 435_790, max_days_past_due_12m: 0, has_current_past_due: false, credit_utilization: 0.59, closed_obligations_count: 3, applications_last_6m: 5 },
    },
    application: { product_type: 'overdraft', requested_amount_rub: 1_500_000, term_months: 12, purpose: 'working_capital', segment: 'small' },
  },
  {
    key: 'd',
    title: 'ИП Компания 7622',
    scenario: 'Продукт не выбран → банк подберёт его сам',
    email: 'company-d@demo.simplecredits.ru',
    password: 'demo-d-2026',
    username: 'demo_company_d',
    profile: {
      company: { inn: '776043817622', ogrn: '392109517066945', legal_name: 'ИП Компания 7622', legal_form: 'individual_entrepreneur', okved: '46.90', region: 'Екатеринбург', registration_date: daysAgo(3234), employee_count: 11 },
      financials: { annual_revenue_rub: 2_400_000, annual_net_profit_rub: 300_000, ebitda_rub: 420_000, total_debt_rub: 0, monthly_revenue_rub: 200_000, monthly_expenses_rub: 165_000, accounts_receivable_rub: 120_000, cash_balance_rub: 250_000, period_end: period },
      credit_history: { active_obligations_count: 0, total_outstanding_rub: 0, monthly_debt_payments_rub: 0, max_days_past_due_12m: 0, has_current_past_due: false, credit_utilization: 0, closed_obligations_count: 2, applications_last_6m: 2 },
    },
    application: { product_type: null, requested_amount_rub: 500_000, term_months: 12, purpose: 'equipment', segment: 'micro' },
  },
  {
    key: 'e',
    title: 'ООО Компания 1178',
    scenario: 'Текущая просрочка в БКИ → отказ с объяснением',
    email: 'company-e@demo.simplecredits.ru',
    password: 'demo-e-2026',
    username: 'demo_company_e',
    profile: {
      company: { inn: '7754811178', ogrn: '1255099648783', legal_name: 'ООО Компания 1178', legal_form: 'llc', okved: '62.01', region: 'Москва', registration_date: daysAgo(586), employee_count: 83 },
      financials: { annual_revenue_rub: 18_000_000, annual_net_profit_rub: -600_000, ebitda_rub: 400_000, total_debt_rub: 4_259_182, monthly_revenue_rub: 1_500_000, monthly_expenses_rub: 1_560_000, accounts_receivable_rub: 2_600_000, cash_balance_rub: 150_000, period_end: period },
      credit_history: { active_obligations_count: 2, total_outstanding_rub: 4_259_182, monthly_debt_payments_rub: 224_428, max_days_past_due_12m: 79, has_current_past_due: true, credit_utilization: 0.41, closed_obligations_count: 2, applications_last_6m: 6 },
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
