import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// base: './' — сборку можно открыть с любого пути (Docker/nginx, статический хостинг демо)
export default defineConfig({
  base: './',
  plugins: [react()],
  server: { port: 5173, host: true },
  build: { outDir: 'dist', sourcemap: false, chunkSizeWarningLimit: 1500 },
});
