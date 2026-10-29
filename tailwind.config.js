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
        slate: { 850: '#182236', 900: '#131c2e', 950: '#0b111e' },
        pas: {
          canvas: 'var(--pas-bg-canvas)',
          surface: 'var(--pas-bg-surface)',
          inset: 'var(--pas-bg-surface-inset)',
          muted: 'var(--pas-bg-surface-muted)',
          elevated: 'var(--pas-bg-surface-elevated)',
          border: 'var(--pas-border-subtle)',
          'border-strong': 'var(--pas-border-strong)',
          primary: 'var(--pas-text-primary)',
          secondary: 'var(--pas-text-secondary)',
          tertiary: 'var(--pas-text-tertiary)',
          brass: 'var(--pas-accent-brass)',
          cobalt: 'var(--pas-accent-cobalt)',
          patina: 'var(--pas-accent-patina)',
          oxide: 'var(--pas-accent-oxide)'
        }
      }
    }
  },
  plugins: [],
};
