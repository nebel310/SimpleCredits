import { expect, type Page } from '@playwright/test';

export const DEMO = {
  a: 'ИП «Компания A»',
  b: 'ООО «Компания B»',
  c: 'ООО «Компания C»',
  d: 'ИП «Компания D»',
  e: 'ООО «Компания E»',
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

/** Отправить форму новой заявки и дождаться карточки */
export async function submitApplication(page: Page) {
  await page.getByText('Согласие на обработку персональных данных', { exact: true }).click();
  await page.getByText('Согласие на запрос кредитной истории в БКИ', { exact: true }).click();
  await page.getByRole('button', { name: 'Отправить заявку' }).click();
  await expect(page).toHaveURL(/#\/applications\/[0-9a-f]{32}/, { timeout: 30_000 });
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

/** Заполнить профиль: реквизиты и кредитная история из моков бэкенда, финансы вручную */
export async function fillProfile(page: Page, inn = '7701234567') {
  await page.getByLabel('ИНН').fill(inn);
  await page.getByRole('button', { name: 'Найти в ЕГРЮЛ' }).click();
  await expect(page.getByLabel('Название')).not.toHaveValue('');
  await page.getByRole('button', { name: 'Запросить в БКИ' }).click();
  await expect(page.getByLabel('Действующих кредитов')).not.toHaveValue('');
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
  await expect(page.getByText('Профиль сохранён')).toBeVisible();
}
