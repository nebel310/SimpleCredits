import { expect, test } from '@playwright/test';
import { DEMO, demoLogin, freshClientLikeA, logout, openLastApplication, submitApplication } from './helpers';

// Пять демо-компаний — пять разных исходов: одобрение с оформлением, другие условия,
// ручная проверка с решением банка, подбор продукта банком и отказ

test('демо-аккаунт A входит одной кнопкой, оборотный кредит выбран заранее', async ({ page }) => {
  await demoLogin(page, DEMO.a);
  await page.goto('./#/apply');
  await expect(page.locator('.choice[aria-pressed=true]')).toContainText('Оборотный кредит');
});

test('A — одобрено, клиент принимает предложение и оформляет кредит', async ({ page }) => {
  // новый клиент с финансами как у A и своей компанией: выданные кредиты считаются по ИНН,
  // поэтому у демо-компании A с каждым прогоном росла бы нагрузка
  await freshClientLikeA(page);
  await page.goto('./#/apply');
  await page.locator('.choice').filter({ has: page.getByText('Оборотный кредит', { exact: true }) }).click();
  await page.getByLabel('Сумма').fill('3000000');
  await submitApplication(page);
  await expect(page.getByRole('heading', { name: 'Заявка одобрена' })).toBeVisible();
  await expect(page.getByText('Получены данные: ЕГРЮЛ, ФНС, БКИ')).toBeVisible();
  // клиент видит категорию риска, условия и калькулятор, но не балл и PD
  await expect(page.getByText('Категория: низкий риск')).toBeVisible();
  await expect(page.getByText('Скоринговый балл')).toHaveCount(0);
  await expect(page.getByRole('heading', { name: 'Условия предложения' })).toBeVisible();
  await expect(page.getByText('Предварительный расчёт. Условия банка не меняются.')).toBeVisible();
  // принять → подтвердить и оформить
  await page.getByRole('button', { name: 'Принять предложение' }).click();
  await expect(page.getByRole('heading', { name: 'Предложение принято' })).toBeVisible();
  await page.getByRole('button', { name: 'Подтвердить и оформить' }).click();
  await page.getByRole('dialog').getByRole('button', { name: 'Подтвердить и оформить' }).click();
  await expect(page.getByRole('heading', { name: 'Кредит оформлен' })).toBeVisible();
  await expect(page.locator('.banner')).toContainText(/Договор № SC-\d{8}-[0-9A-F]{6}/);
  await expect(page.getByText(/Кредит оформлен, договор № SC-/)).toBeVisible();
  await expect(page.getByRole('button', { name: 'Принять предложение' })).toHaveCount(0);
});

test('B — меньшая сумма: другие условия, клиент принимает', async ({ page }) => {
  await demoLogin(page, DEMO.b);
  await page.goto('./#/apply');
  await submitApplication(page);
  await expect(page.getByRole('heading', { name: 'Предлагаем другие условия' })).toBeVisible();
  await expect(page.getByText('Запрошенная сумма больше 60% годовой выручки')).toBeVisible();
  await expect(page.locator('.banner')).toContainText('15 000 000');
  await page.getByRole('button', { name: 'Принять предложение' }).click();
  await expect(page.getByRole('heading', { name: 'Предложение принято' })).toBeVisible();
});

test('C — ручная проверка: не оффер, решение принимает сотрудник банка', async ({ page }) => {
  await demoLogin(page, DEMO.c);
  await page.goto('./#/apply');
  await submitApplication(page);
  await expect(page.getByRole('heading', { name: 'Нужна дополнительная проверка' })).toBeVisible();
  await expect(page.getByText('Оценка риска в пограничной зоне')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Принять предложение' })).toHaveCount(0);
  await logout(page);

  // банк: фильтр «Ждут проверки» → карточка → решение
  await demoLogin(page, DEMO.bank);
  await page.getByRole('button', { name: /^Ждут проверки · \d+/ }).click();
  await page.locator('tbody tr', { hasText: DEMO.c }).first().click();
  await expect(page.getByRole('heading', { name: 'Решение по заявке' })).toBeVisible();
  await page.getByText('Одобрить с другой суммой').click();
  await page.getByLabel('Сумма, которую одобряет банк').fill('1000000');
  await page.getByLabel('Комментарий для клиента').fill('Одобряем лимит поменьше — с учётом текущей нагрузки');
  await page.getByRole('button', { name: 'Сохранить решение' }).click();
  await expect(page.locator('.banner .chip')).toHaveText('Предлагаем другие условия');
  await logout(page);

  // клиент видит решение банка и может принять предложение
  await demoLogin(page, DEMO.c);
  await openLastApplication(page);
  await expect(page.getByRole('heading', { name: 'Предлагаем другие условия' })).toBeVisible();
  await expect(page.getByText('Одобряем лимит поменьше — с учётом текущей нагрузки')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Принять предложение' })).toBeVisible();
});

test('D — продукт не выбран, банк подобрал сам', async ({ page }) => {
  await demoLogin(page, DEMO.d);
  await page.goto('./#/apply');
  await expect(page.locator('.choice[aria-pressed=true]')).toContainText('Подобрать за меня');
  await expect(page.locator('.choice[aria-pressed=true]')).toContainText('Лизинг оборудования');
  await submitApplication(page);
  await expect(page.getByRole('heading', { name: 'Подобрали продукт' })).toBeVisible();
  await expect(page.getByText('подобран банком')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Принять предложение' })).toBeVisible();
});

test('E — текущая просрочка: отказ с причиной и советом', async ({ page }) => {
  await demoLogin(page, DEMO.e);
  await page.goto('./#/apply');
  await submitApplication(page);
  await expect(page.getByRole('heading', { name: 'Банк отказал' })).toBeVisible();
  await expect(page.locator('.banner')).toContainText('сейчас есть просрочка по кредитам');
  await expect(page.getByText('Что делать дальше')).toBeVisible();
  await expect(page.getByText(/Погасите текущую просрочку/).first()).toBeVisible();
  await expect(page.getByRole('button', { name: 'Новая заявка' })).toBeVisible();
});
