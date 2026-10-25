import { expect, test } from '@playwright/test';
import { DEMO, demoLogin, fillProfile, register, submitApplication } from './helpers';

test('без профиля заявку отправить нельзя — сначала профиль', async ({ page }) => {
  await register(page);
  await page.goto('./#/apply');
  await expect(page.getByRole('heading', { name: 'Сначала заполните профиль компании' })).toBeVisible();
  await page.getByRole('button', { name: 'Заполнить профиль' }).click();
  await expect(page).toHaveURL(/#\/profile\?next=apply/);
});

test('профиль: проверки полей, подстановка из ЕГРЮЛ и БКИ, затем заявка', async ({ page }) => {
  await register(page);
  // ИНН неправильной длины — поиск в ЕГРЮЛ недоступен
  await page.getByLabel('ИНН').fill('123');
  await expect(page.getByRole('button', { name: 'Найти в ЕГРЮЛ' })).toBeDisabled();
  // пустой профиль не сохраняется
  await page.getByRole('button', { name: 'Сохранить профиль' }).click();
  await expect(page.getByText('Заполните отмеченные поля')).toBeVisible();
  await expect(page.getByText('ИНН — 10 цифр для ООО или 12 для ИП')).toBeVisible();
  // загрузка лимитов больше 100% — ошибка
  await page.getByLabel('Использование кредитных лимитов, %').fill('150');
  await expect(page.getByText('От 0 до 100%')).toBeVisible();
  await page.getByLabel('Использование кредитных лимитов, %').fill('40');
  await fillProfile(page);
  // в форме заявки — данные компании из профиля
  await page.goto('./#/apply');
  await expect(page.getByText('Данные компании')).toBeVisible();
  await page.locator('.choice', { hasText: 'Микрозайм' }).click();
  await page.getByLabel('Сумма').fill('900000');
  await submitApplication(page);
  await expect(page.locator('.banner h2')).toBeVisible();
});

test('даты в профиле не могут быть в будущем', async ({ page }) => {
  await register(page);
  await page.getByLabel('Дата регистрации').fill('2099-01-01');
  await page.getByRole('button', { name: 'Сохранить профиль' }).click();
  await expect(page.getByText('Дата регистрации не может быть в будущем')).toBeVisible();
});

test('без выбора продукта сумма и срок — в границах каталога', async ({ page }) => {
  await demoLogin(page, DEMO.d);
  await page.goto('./#/apply');
  await expect(page.locator('.choice[aria-pressed=true]')).toContainText('Подобрать за меня');
  await page.getByLabel('Сумма').fill('1');
  await page.getByLabel('Срок, месяцев').fill('120');
  await page.getByRole('button', { name: 'Отправить заявку' }).click();
  await expect(page.getByText('По нашим продуктам — от 50 000 ₽ до 50 000 000 ₽')).toBeVisible();
  await expect(page.getByText('По нашим продуктам — от 1 до 60 месяцев')).toBeVisible();
  await expect(page).toHaveURL(/#\/apply/);
});

test('убыток вводится со знаком минус', async ({ page }) => {
  await register(page);
  await page.getByLabel('Чистая прибыль за год').fill('-250000');
  await expect(page.getByLabel('Чистая прибыль за год')).toHaveValue('−250 000');
});

test('форма заявки: границы суммы и срока по продукту, сегмент и цели', async ({ page }) => {
  await demoLogin(page, DEMO.a);
  await page.goto('./#/apply');
  await page.locator('.choice', { hasText: 'Микрозайм' }).click();
  // подсказка — в рублях, без «0,1 млн»
  await expect(page.getByText('От 50 000 ₽ до 3 000 000 ₽')).toBeVisible();
  // микрозайм только для микробизнеса
  await expect(page.getByText('Продукт «Микрозайм» — только для сегмента «микробизнес»')).toBeVisible();
  await page.getByLabel('Сумма').fill('100');
  await page.getByLabel('Срок, месяцев').fill('48');
  await page.getByRole('button', { name: 'Отправить заявку' }).click();
  await expect(page.getByText('Для продукта «Микрозайм» — от 50 000 ₽ до 3 000 000 ₽')).toBeVisible();
  await expect(page.getByText('Для продукта «Микрозайм» — от 1 до 24 месяцев')).toBeVisible();
  // пока ошибки не исправлены, заявка не уходит
  await expect(page).toHaveURL(/#\/apply/);
});
