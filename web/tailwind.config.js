/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        grass: { 100: '#f0fdf4', 200: '#bbf7d0', 300: '#86efac', 400: '#4ade80', 500: '#22c55e', 600: '#16a34a', 700: '#15803d', 800: '#166534', 900: '#14532d' },
        sky: { 100: '#e0f2fe', 200: '#bae6fd', 300: '#7dd3fc', 400: '#38bdf8', 500: '#0ea5e9', 600: '#0284c7' },
        flower: { pink: '#f472b6', yellow: '#fbbf24', orange: '#fb923c', purple: '#c084fc', red: '#f87171' },
        wood: { 200: '#fef3c7', 300: '#fde68a', 400: '#fcd34d', 500: '#f59e0b', 600: '#d97706', 700: '#b45309' },
        slide: { 300: '#a5f3fc', 400: '#22d3ee', 500: '#06b6d4', 600: '#0891b2' },
      },
      fontFamily: {
        hand: ['"Comic Neue"', 'cursive', 'system-ui'],
        mono: ['"JetBrains Mono"', 'monospace'],
      },
      animation: {
        'float': 'float 3s ease-in-out infinite',
        'sway': 'sway 4s ease-in-out infinite',
        'bounce-slow': 'bounce 2s ease-in-out infinite',
        'flutter': 'flutter 0.5s ease-in-out infinite alternate',
        'wiggle': 'wiggle 1s ease-in-out infinite',
        'grow': 'grow 0.5s ease-out',
      },
      keyframes: {
        float: { '0%, 100%': { transform: 'translateY(0px)' }, '50%': { transform: 'translateY(-10px)' } },
        sway: { '0%, 100%': { transform: 'rotate(-5deg)' }, '50%': { transform: 'rotate(5deg)' } },
        flutter: { '0%': { transform: 'rotate(-10deg) translateY(0px)' }, '100%': { transform: 'rotate(10deg) translateY(-5px)' } },
        wiggle: { '0%, 100%': { transform: 'rotate(-3deg)' }, '50%': { transform: 'rotate(3deg)' } },
        grow: { '0%': { transform: 'scaleY(0)', opacity: '0' }, '100%': { transform: 'scaleY(1)', opacity: '1' } },
      },
    },
  },
  plugins: [],
}
