import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import { resolve } from 'node:path';

export default defineConfig({
    plugins: [tailwindcss(), react()],
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
    build: {
        rollupOptions: {
            input: {
                main: resolve(__dirname, 'index.html'),
                showcase: resolve(__dirname, 'lib-showcase.html'),
            },
        },
    },
    test: {
        environment: 'jsdom',
        globals: true,
        setupFiles: ['./src/test-setup.ts'],
    },
});
