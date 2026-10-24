import { expect, test } from '@playwright/test';
import { DEMO, demoLogin, submitApplication } from './helpers';

// Пять демо-компаний — пять разных исходов ML-модели (USERFLOW §5)

test('A — одобрено на запрошенных условиях', async ({ page }) => {
  await demoLogin(page, DEMO.a);
  await page.goto('./#/apply');
  await expect(page.locator('.choice[aria-pressed=true]')).toContainText('Оборотный кредит');
  await submitApplication(page);
  await expect(page.getByRole('heading', { name: 'Заявка одобрена' })).toBeVisible();
  await expect(page.getByText('Получены данные: ЕГРЮЛ, ФНС, БКИ')).toBeVisible();
  await expect(page.getByText('Скоринговый балл')).toBeVisible();
});

test('B — меньшая сумма, повторная заявка на неё одобрена', async ({ page }) => {
  await demoLogin(page, DEMO.b);
  await page.goto('./#/apply');
  await submitApplication(page);
  await expect(page.getByRole('heading', { name: 'Можем одобрить на других условиях' })).toBeVisible();
  await expect(page.getByText('Запрошенная сумма больше 60% годовой выручки')).toBeVisible();
  await page.getByRole('button', { name: /Подать заявку на 15/ }).click();
  await expect(page).toHaveURL(/#\/apply\?product=credit_line&amount=15000000/);
  await expect(page.locator('.red-card')).toContainText('15 000 000');
  await submitApplication(page);
  await expect(page.getByRole('heading', { name: 'Заявка одобрена' })).toBeVisible();
});

test('C — пограничная зона риска, ручная проверка', async ({ page }) => {
  await demoLogin(page, DEMO.c);
  await page.goto('./#/apply');
  await submitApplication(page);
  await expect(page.getByRole('heading', { name: 'Автоматического решения нет' })).toBeVisible();
  await expect(page.getByText('Оценка риска в пограничной зоне')).toBeVisible();
});

test('D — продукт не выбран, банк подобрал сам', async ({ page }) => {
  await demoLogin(page, DEMO.d);
  await page.goto('./#/apply');
  await expect(page.locator('.choice[aria-pressed=true]')).toContainText('Подобрать за меня');
  await submitApplication(page);
  await expect(page.getByRole('heading', { name: 'Одобрено — продукт подобрали за вас' })).toBeVisible();
});

test('E — текущая просрочка, отказ', async ({ page }) => {
  await demoLogin(page, DEMO.e);
  await page.goto('./#/apply');
  await submitApplication(page);
  await expect(page.getByRole('heading', { name: 'Банк отказал' })).toBeVisible();
  await expect(page.getByText('Сейчас есть просрочка по кредитам')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Новая заявка' })).toBeVisible();
});
