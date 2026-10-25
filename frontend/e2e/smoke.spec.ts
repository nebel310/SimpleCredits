import { expect, test } from '@playwright/test';
import { DEMO, demoLogin, logout } from './helpers';

// На всех экранах нет ошибок JavaScript и горизонтальной прокрутки (десктоп и телефон)
for (const viewport of [{ width: 1440, height: 900 }, { width: 375, height: 812 }]) {
  test(`экраны без ошибок и горизонтальной прокрутки — ${viewport.width}px`, async ({ page }) => {
    await page.setViewportSize(viewport);
    const errors: string[] = [];
    page.on('pageerror', (e) => errors.push(String(e)));
    const noOverflow = async (where: string) => {
      const extra = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
      expect(extra, `горизонтальная прокрутка на ${where}`).toBeLessThanOrEqual(0);
    };
    await page.goto('./#/login');
    await noOverflow('входе');
    await demoLogin(page, DEMO.a);
    for (const path of ['#/home', '#/products', '#/profile', '#/apply', '#/applications']) {
      await page.goto(`./${path}`);
      await expect(page.locator('h1')).toBeVisible();
      await noOverflow(path);
    }
    await logout(page);
    await demoLogin(page, DEMO.bank);
    await expect(page.getByText('Всего заявок')).toBeVisible();
    await noOverflow('#/bank');
    expect(errors).toEqual([]);
  });
}
