import js from '@eslint/js';
import tseslint from 'typescript-eslint';
import pluginReact from 'eslint-plugin-react';
import pluginReactHooks from 'eslint-plugin-react-hooks';
import pluginJsxA11y from 'eslint-plugin-jsx-a11y';
import prettierConfig from 'eslint-config-prettier';
import globals from 'globals';

export default tseslint.config(
    // ── Ignore patterns ────────────────────────────────────────────────────
    {
        ignores: [
            'dist/**',
            'node_modules/**',
            '**/*.config.js',
            'coverage/**',
            'public/sounds/**',
        ],
    },

    // ── Base JS recommended (all files) ────────────────────────────────────
    js.configs.recommended,

    // ── TypeScript recommended (type-checked) — TS/TSX only ────────────────
    ...tseslint.configs.recommendedTypeChecked.map((cfg) => ({
        ...cfg,
        files: ['**/*.{ts,tsx}'],
    })),

    // ── React flat/recommended — TS/TSX/JS/JSX ─────────────────────────────
    {
        ...pluginReact.configs.flat.recommended,
        files: ['**/*.{ts,tsx,js,jsx}'],
    },

    // ── React Hooks ─────────────────────────────────────────────────────────
    {
        ...pluginReactHooks.configs.flat['recommended-latest'],
        files: ['**/*.{ts,tsx,js,jsx}'],
    },

    // ── JSX A11y ────────────────────────────────────────────────────────────
    {
        ...pluginJsxA11y.flatConfigs.recommended,
        files: ['**/*.{ts,tsx,js,jsx}'],
    },

    // ── Language options & settings for TS/TSX ──────────────────────────────
    {
        files: ['**/*.{ts,tsx}'],
        languageOptions: {
            globals: {
                ...globals.browser,
                ...globals.node,
            },
            parserOptions: {
                project: ['./tsconfig.json', './tsconfig.node.json'],
                tsconfigRootDir: import.meta.dirname,
            },
        },
        settings: {
            react: {
                version: '19.2.4',
            },
        },
        rules: {
            // React 19 — no need to import React in scope
            'react/react-in-jsx-scope': 'off',

            // Allow _-prefixed vars as intentionally unused
            '@typescript-eslint/no-unused-vars': [
                'warn',
                {
                    argsIgnorePattern: '^_',
                    varsIgnorePattern: '^_',
                    caughtErrorsIgnorePattern: '^_',
                },
            ],
        },
    },

    // ── Language options for plain JS/JSX ───────────────────────────────────
    {
        files: ['**/*.{js,jsx,mjs,cjs}'],
        languageOptions: {
            globals: {
                ...globals.browser,
                ...globals.node,
            },
        },
        settings: {
            react: {
                version: '19.2.4',
            },
        },
        rules: {
            // Disable TS-only rules for plain JS files
            '@typescript-eslint/no-unsafe-assignment': 'off',
            '@typescript-eslint/no-unsafe-call': 'off',
            '@typescript-eslint/no-unsafe-member-access': 'off',
            '@typescript-eslint/no-unsafe-return': 'off',
            '@typescript-eslint/no-unsafe-argument': 'off',
            '@typescript-eslint/no-require-imports': 'off',
        },
    },

    // ── Relax unused-vars rule in test files ────────────────────────────────
    {
        files: ['**/__tests__/**/*.{ts,tsx}', '**/*.test.{ts,tsx}'],
        rules: {
            '@typescript-eslint/no-unused-vars': 'off',
        },
    },

    // ── Layer boundary rules (warn-only — existing code has violations) ─────
    {
        files: ['**/*.{ts,tsx}'],
        rules: {
            // Disallow deep cross-feature imports: @features/foo/bar/baz
            // (only @features/foo/index or @features/foo are allowed).
            'no-restricted-imports': [
                'warn',
                {
                    patterns: [
                        {
                            // Match @features/<name>/<anything>/<anything-else>
                            // i.e. more than one level deep — only allow @features/<name> or
                            // @features/<name>/index.
                            group: ['@features/*/*/**', '@features/*/!(index)'],
                            message:
                                'Cross-feature deep imports are not allowed. ' +
                                'Import from @features/<name> or @features/<name>/index only.',
                        },
                        {
                            // Disallow deep @ui imports except @ui itself and @ui/orb/*
                            group: ['@ui/**', '!@ui/orb/**'],
                            message:
                                'Deep @ui imports are not allowed. ' +
                                'Use the @ui barrel or @ui/orb/* only.',
                        },
                    ],
                },
            ],
            // Warn on direct `new WebSocket(...)` calls outside core/websocket/
            'no-restricted-syntax': [
                'warn',
                {
                    selector:
                        "NewExpression[callee.name='WebSocket']:not([callee.object.name='WebSocket'])",
                    message:
                        'Do not instantiate WebSocket directly. Use wsClient from @core/websocket.',
                },
            ],
        },
    },

    // Allow new WebSocket() in core/websocket/wsClient.ts without warning
    {
        files: ['**/core/websocket/wsClient.ts'],
        rules: {
            'no-restricted-syntax': 'off',
        },
    },

    // ── Prettier LAST — disables conflicting formatting rules ───────────────
    prettierConfig,
);
