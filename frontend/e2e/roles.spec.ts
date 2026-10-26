import { expect, test } from '@playwright/test';
import { DEMO, demoLogin, freshClientLikeA, logout, submitApplication } from './helpers';

test('без входа любой адрес ведёт на экран входа', async ({ page }) => {
  for (const path of ['#/home', '#/apply', '#/applications', '#/bank', '#/profile']) {
    await page.goto(`./${path}`);
    await expect(page).toHaveURL(/#\/login/);
  }
});

test('клиент не попадает в кабинет банка, банк — в кабинет клиента', async ({ page }) => {
  await demoLogin(page, DEMO.a);
  await page.goto('./#/bank');
  await expect(page).toHaveURL(/#\/home/);
  await logout(page);
  await demoLogin(page, DEMO.bank);
  await page.goto('./#/home');
  await expect(page).toHaveURL(/#\/bank/);
});

test('карточка заявки открывается по прямой ссылке и после обновления страницы', async ({ page }) => {
  await freshClientLikeA(page);
  await page.goto('./#/apply');
  await page.locator('.choice').filter({ has: page.getByText('Оборотный кредит', { exact: true }) }).click();
  await page.getByLabel('Сумма').fill('3000000');
  await submitApplication(page);
  const url = page.url();
  await page.reload();
  await expect(page.getByRole('heading', { name: 'Заявка одобрена' })).toBeVisible();
  await page.goto('./#/home');
  await page.goto(url);
  await expect(page.getByRole('heading', { name: 'Заявка одобрена' })).toBeVisible();
});

test('несуществующая заявка — понятная ошибка', async ({ page }) => {
  await demoLogin(page, DEMO.a);
  await page.goto('./#/applications/00000000000000000000000000000000');
  await expect(page.getByText('Заявка не найдена')).toBeVisible();
});

test('выход завершает сессию', async ({ page }) => {
  await demoLogin(page, DEMO.a);
  await logout(page);
  await page.goto('./#/applications');
  await expect(page).toHaveURL(/#\/login/);
});

test('кабинет банка: статистика, модель, карточка заявки без кнопок клиента', async ({ page }) => {
  await demoLogin(page, DEMO.bank);
  await expect(page.getByText('Всего заявок')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Скоринговая модель' })).toBeVisible();
  await expect(page.getByText('ROC-AUC (тест)')).toBeVisible();
  await page.locator('tbody tr').first().click();
  await expect(page).toHaveURL(/#\/bank\/applications\/[0-9a-f]{32}/);
  await expect(page.getByText('Решение скоринга')).toBeVisible();
  await expect(page.getByRole('button', { name: /Подать заявку|Новая заявка|Принять предложение|Отказаться/ })).toHaveCount(0);
});
