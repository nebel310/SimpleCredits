import { expect, test } from '@playwright/test';
import { newUser, register } from './helpers';

test('форма входа проверяет поля до отправки', async ({ page }) => {
  await page.goto('./#/login');
  await page.getByRole('button', { name: 'Войти', exact: true }).first().click();
  await expect(page.getByText('Укажите email, например name@company.ru')).toBeVisible();
  await expect(page.getByText('Введите пароль')).toBeVisible();
});

test('неверный пароль — понятная ошибка от бэкенда', async ({ page }) => {
  await page.goto('./#/login');
  await page.getByLabel('Email').fill('nobody@example.ru');
  await page.getByLabel('Пароль', { exact: true }).fill('wrong');
  await page.getByRole('button', { name: 'Войти', exact: true }).first().click();
  await expect(page.getByText('Неверный email или пароль')).toBeVisible();
});

test('регистрация: пароли должны совпадать', async ({ page }) => {
  await page.goto('./#/login');
  await page.getByRole('tab', { name: 'Регистрация' }).click();
  await page.getByLabel('Имя пользователя').fill('x');
  await page.getByLabel('Email').fill('x@example.ru');
  await page.getByLabel('Пароль', { exact: true }).fill('one');
  await page.getByLabel('Повторите пароль').fill('two');
  await page.getByRole('button', { name: 'Зарегистрироваться' }).click();
  await expect(page.getByText('Пароли не совпадают')).toBeVisible();
});

test('регистрация: пароль не короче 6 символов', async ({ page }) => {
  await page.goto('./#/login');
  await page.getByRole('tab', { name: 'Регистрация' }).click();
  await page.getByLabel('Имя пользователя').fill('x');
  await page.getByLabel('Email').fill('x@example.ru');
  await page.getByLabel('Пароль', { exact: true }).fill('123');
  await page.getByLabel('Повторите пароль').fill('123');
  await page.getByRole('button', { name: 'Зарегистрироваться' }).click();
  await expect(page.getByText('Пароль — не короче 6 символов')).toBeVisible();
});

test('регистрация ведёт в профиль, повторная — ошибка «уже существует»', async ({ page }) => {
  const u = await register(page, newUser());
  await expect(page.getByRole('heading', { name: 'Компания, финансы и кредитная история' })).toBeVisible();
  await page.getByTitle('Выйти из аккаунта').click();
  await page.getByRole('tab', { name: 'Регистрация' }).click();
  await page.getByLabel('Имя пользователя').fill(u.username + 'x');
  await page.getByLabel('Email').fill(u.email);
  await page.getByLabel('Пароль', { exact: true }).fill(u.password);
  await page.getByLabel('Повторите пароль').fill(u.password);
  await page.getByRole('button', { name: 'Зарегистрироваться' }).click();
  await expect(page.getByText(/уже существует/)).toBeVisible();
});
