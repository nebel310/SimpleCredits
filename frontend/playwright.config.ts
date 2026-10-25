import { defineConfig, devices } from '@playwright/test';

// E2E-тесты гоняются против запущенного стека (docker compose up или npm run dev + бэкенд).
// Адрес фронтенда: E2E_BASE_URL, по умолчанию — фронтенд из docker compose.
export default defineConfig({
  testDir: './e2e',
  timeout: 60_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [['list']],
  use: {
    baseURL: process.env.E2E_BASE_URL || 'http://localhost:5500',
    locale: 'ru-RU',
    viewport: { width: 1440, height: 900 },
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 } } }],
});
