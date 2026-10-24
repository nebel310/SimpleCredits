import { loadEnv } from 'vite';
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

// base: './' — сборку можно открыть с любого пути.
// В `npm run dev` и `npm run preview` запросы /api (и WebSocket /api/ws) проксируются на бэкенд — CORS не нужен.
// В Docker то же самое делает nginx (nginx.conf).
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const backend = env.BACKEND_URL || 'http://localhost:3001';
  const proxy = { '/api': { target: backend, changeOrigin: true, ws: true, rewrite: (p: string) => p.replace(/^\/api/, '') } };
  return {
    base: './',
    plugins: [react()],
    server: { port: 5173, host: true, proxy },
    preview: { port: 4173, proxy },
    build: { outDir: 'dist', sourcemap: false, chunkSizeWarningLimit: 1500 },
    // юнит-тесты лежат рядом с кодом в src/, e2e — отдельно в e2e/ (Playwright)
    test: { include: ['src/**/*.test.ts'], environment: 'node' },
  };
});
