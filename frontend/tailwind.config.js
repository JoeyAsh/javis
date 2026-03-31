/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        jarvis: {
          bg: '#050508',
          surface: '#0d0d14',
          'surface-raised': '#12121c',
          border: '#1a1a2e',
          accent: '#4ca8e8',
          'accent-bright': '#6ec4ff',
          'accent-speak': '#5ab8f0',
          text: '#e8f4ff',
          'text-secondary': '#6b8fa8',
          'text-muted': '#2a3d4f',
        },
      },
      fontFamily: {
        mono: ['JetBrains Mono', 'monospace'],
      },
    },
  },
  plugins: [],
};
