import { expect, type Page } from '@playwright/test';

export const DEMO = {
  a: 'ИП Компания 9986',
  b: 'ООО Компания 2785',
  c: 'ООО Компания 7752',
  d: 'ИП Компания 7622',
  e: 'ООО Компания 1178',
  bank: 'Банк · администратор',
};

/** Демо-вход одной кнопкой на экране входа */
export async function demoLogin(page: Page, title: string) {
  await page.goto('./#/login');
  const row = page.locator('div.row-c', { hasText: title }).last();
  await row.getByRole('button', { name: 'Войти' }).click();
  await expect(page).toHaveURL(title === DEMO.bank ? /#\/bank/ : /#\/home/);
}

export async function logout(page: Page) {
  await page.getByTitle('Выйти из аккаунта').click();
  await expect(page).toHaveURL(/#\/login/);
}

/** Открыть карточку последней заявки клиента */
export async function openLastApplication(page: Page) {
  await page.goto('./#/applications');
  await page.locator('tbody tr').first().getByRole('link').click();
  await expect(page).toHaveURL(/#\/applications\/[0-9a-f]{32}/);
}

/** Отправить форму новой заявки и дождаться карточки */
export async function submitApplication(page: Page) {
  await page.getByText('Согласие на обработку персональных данных', { exact: true }).click();
  await page.getByText('Согласие на запрос кредитной истории в БКИ', { exact: true }).click();
  await page.getByRole('button', { name: 'Отправить заявку' }).click();
  await expect(page).toHaveURL(/#\/applications\/[0-9a-f]{32}/, { timeout: 30_000 });
}

/**
 * ИНН компаний, у которых в мок-БКИ чистая история (без кредитов и просрочек), а сами они
 * работают больше года. Мок отвечает по ИНН детерминированно; с финансами как у A каждая из них
 * одобряется с запасом (проверено скорингом). Банк учитывает кредиты, уже выданные компании
 * (по ИНН), поэтому тест берёт случайную компанию из списка — прогоны не копят нагрузку на одном ИНН.
 */
const CLEAN_INNS = ['770007056148', '776484473097', '772508996141', '770791863390', '777196010057', '779092283454', '773157997267', '774878146819', '771811064642', '778370676645', '771896239822', '776338805448', '778241527495', '774676369447', '772480903669', '777516460306', '773731688557', '777565192948', '774383313522', '774433090648', '776576785728', '778333241386', '779037638125', '777852965623', '775011845732', '771768924747', '771813738942', '777924696325', '775807309316', '777716979678', '774848186896', '774096103113', '772110822059', '771914080281', '779381965796', '771784520472', '774008392762', '776823621527', '774455229895', '771351860678'];

async function cleanCompany(page: Page) {
  const inn = CLEAN_INNS[Math.floor(Math.random() * CLEAN_INNS.length)];
  const e = await (await page.request.get(`api/mock/egrul/${inn}`)).json();
  const b = await (await page.request.get(`api/mock/bki/${inn}`)).json();
  return { e, b };
}

/**
 * Новый клиент с финансами как у демо-компании A и своей компанией с чистой историей.
 * Сценарий одобрения повторяется при любом числе прогонов на одной базе.
 */
export async function freshClientLikeA(page: Page) {
  const u = newUser();
  const { e, b } = await cleanCompany(page);
  await page.request.post('api/auth/register', { data: { username: u.username, email: u.email, password: u.password, password_confirm: u.password } });
  const tokens = await (await page.request.post('api/auth/login', { data: { email: u.email, password: u.password } })).json();
  const profile = await page.request.patch('api/auth/me', {
    headers: { Authorization: `Bearer ${tokens.access_token}` },
    data: {
      company: { inn: e.inn, ogrn: e.ogrn, legal_name: e.legal_name, legal_form: e.legal_form, okved: e.okved, region: e.region, registration_date: e.registration_date, employee_count: e.employee_count },
      financials: { annual_revenue_rub: 48_000_000, annual_net_profit_rub: 5_600_000, ebitda_rub: 8_100_000, total_debt_rub: 0, monthly_revenue_rub: 4_000_000, monthly_expenses_rub: 3_300_000, accounts_receivable_rub: 1_400_000, cash_balance_rub: 2_200_000, period_end: '2026-09-30T00:00:00Z' },
      credit_history: { active_obligations_count: 0, total_outstanding_rub: 0, monthly_debt_payments_rub: 0, max_days_past_due_12m: 0, has_current_past_due: false, credit_utilization: 0, closed_obligations_count: b.closed_obligations_count, applications_last_6m: b.applications_last_6m },
    },
  });
  expect(profile.ok()).toBe(true);
  await page.goto('./#/login');
  await page.getByLabel('Email').fill(u.email);
  await page.getByLabel('Пароль', { exact: true }).fill(u.password);
  await page.getByRole('button', { name: 'Войти', exact: true }).first().click();
  await expect(page).toHaveURL(/#\/home/);
}

/** Уникальный пользователь для тестов регистрации */
export function newUser() {
  const id = `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`;
  return { username: `e2e_${id}`, email: `e2e_${id}@example.ru`, password: 'secret123' };
}

export async function register(page: Page, u = newUser()) {
  await page.goto('./#/login');
  await page.getByRole('tab', { name: 'Регистрация' }).click();
  await page.getByLabel('Имя пользователя').fill(u.username);
  await page.getByLabel('Email').fill(u.email);
  await page.getByLabel('Пароль', { exact: true }).fill(u.password);
  await page.getByLabel('Повторите пароль').fill(u.password);
  await page.getByRole('button', { name: 'Зарегистрироваться' }).click();
  await expect(page).toHaveURL(/#\/profile/);
  return u;
}

/** Заполнить профиль: реквизиты из ЕГРЮЛ, кредитная история из БКИ (подтягивается сама), финансы вручную */
export async function fillProfile(page: Page, inn = '7701234567') {
  await page.getByLabel('ИНН').fill(inn);
  await page.getByRole('button', { name: 'Найти в ЕГРЮЛ' }).click();
  await expect(page.getByLabel('Название')).not.toHaveValue('');
  await expect(page.getByLabel('Кредитная история из БКИ')).toBeVisible();
  const fin: Record<string, string> = {
    'Выручка за год': '36000000',
    'Чистая прибыль за год': '2000000',
    'EBITDA за год': '3500000',
    'Общий долг': '4000000',
    'Выручка в месяц': '3000000',
    'Расходы в месяц': '2600000',
    'Дебиторская задолженность': '1000000',
    'Деньги на счетах': '900000',
  };
  for (const [label, value] of Object.entries(fin)) await page.getByLabel(label).fill(value);
  await page.getByLabel('Отчётный период по').fill('2026-09-30');
  await page.getByRole('button', { name: 'Сохранить профиль' }).click();
  await expect(page.getByText('Профиль сохранён').first()).toBeVisible();
}
