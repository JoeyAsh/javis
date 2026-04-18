import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/jarvis-ws': {
        target: 'http://localhost:8765',
        ws: true,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/jarvis-ws/, '/ws'),
      },
      '/voices': {
        target: 'http://localhost:8766',
        changeOrigin: true,
      },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test-setup.ts'],
  },
});
