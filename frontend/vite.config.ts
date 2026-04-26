import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import { resolve } from 'node:path';

export default defineConfig({
    plugins: [tailwindcss(), react()],
    resolve: {
        alias: [
            // @app (bare) → barrel. Regex ensures only the exact bare import matches.
            {
                find: /^@app$/,
                replacement: resolve(__dirname, 'src/app/index.ts'),
            },
            // @app/* → src/app/<rest>
            {
                find: /^@app\/(.*)/,
                replacement: resolve(__dirname, 'src/app') + '/$1',
            },
            // @ui (bare) → barrel
            {
                find: /^@ui$/,
                replacement: resolve(__dirname, 'src/ui/index.ts'),
            },
            // @ui/* → src/ui/<rest>
            {
                find: /^@ui\/(.*)/,
                replacement: resolve(__dirname, 'src/ui') + '/$1',
            },
            // @features/* → src/features/<rest>
            {
                find: /^@features\/(.*)/,
                replacement: resolve(__dirname, 'src/features') + '/$1',
            },
            // @core/* → src/core/<rest>
            {
                find: /^@core\/(.*)/,
                replacement: resolve(__dirname, 'src/core') + '/$1',
            },
            // @common/* → src/common/<rest>
            {
                find: /^@common\/(.*)/,
                replacement: resolve(__dirname, 'src/common') + '/$1',
            },
            // @test/* → src/test/<rest>
            {
                find: /^@test\/(.*)/,
                replacement: resolve(__dirname, 'src/test') + '/$1',
            },
        ],
    },
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
            '/api': {
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
        setupFiles: ['./src/test/setup.ts'],
        environmentOptions: {
            jsdom: {
                url: 'http://localhost',
            },
        },
    },
});
