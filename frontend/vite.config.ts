import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import { resolve } from 'node:path';

export default defineConfig(({ mode }) => {
    const env = loadEnv(mode, process.cwd(), 'VITE_');
    const host = env.VITE_BACKEND_HOST || '127.0.0.1';
    const httpPort = env.VITE_BACKEND_HTTP_PORT || '8766';
    const wsPort = env.VITE_BACKEND_WS_PORT || '8765';
    const httpTarget = `http://${host}:${httpPort}`;
    const wsTarget = `http://${host}:${wsPort}`;

    return {
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
                    target: wsTarget,
                    ws: true,
                    changeOrigin: true,
                    rewrite: (path) => path.replace(/^\/jarvis-ws/, '/ws'),
                },
                '/voices': {
                    target: httpTarget,
                    changeOrigin: true,
                },
                '/api': {
                    target: httpTarget,
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
    };
});
