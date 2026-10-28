/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: 'class',
  content: [
    "./src/paslood/delivery/web/templates/**/*.html",
    "./src/paslood/delivery/web/static/js/**/*.js",
    "./src/paslood/delivery/web/static/i18n.js",
  ],
  theme: {
    extend: {
      colors: {
        brand: { 50: '#eff6ff', 500: '#3b82f6', 600: '#2563eb', 700: '#1d4ed8' },
        slate: { 850: '#151e2e', 900: '#0f172a', 950: '#080d1a' }
      }
    }
  },
  plugins: [],
};
