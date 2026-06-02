/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        display: ['"Outfit"', '"Poppins"', 'sans-serif'],
        body: ['"Poppins"', '"Outfit"', 'sans-serif'],
      },
      colors: {
        cyber: {
          bg: '#0f0f1e',
          card: '#1a1a2e',
          primary: '#6366f1',
          accent: '#06b6d4',
          text: '#e0e7ff',
          'text-secondary': '#a5b4fc',
          'text-muted': '#7c7faa',
          border: 'rgba(165, 180, 252, 0.2)',
        },
      },
      borderRadius: {
        glass: '16px',
        pill: '20px',
      },
      keyframes: {
        'fade-in-up': {
          from: { opacity: '0', transform: 'translateY(20px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        'fade-in-scale': {
          from: { opacity: '0', transform: 'scale(0.95)' },
          to: { opacity: '1', transform: 'scale(1)' },
        },
        'glow-pulse': {
          '0%, 100%': { boxShadow: '0 0 20px rgba(99, 102, 241, 0.4), 0 0 40px rgba(6, 182, 212, 0.2)' },
          '50%': { boxShadow: '0 0 30px rgba(99, 102, 241, 0.6), 0 0 60px rgba(6, 182, 212, 0.3)' },
        },
        'float-gentle': {
          '0%, 100%': { transform: 'translateY(0px)' },
          '50%': { transform: 'translateY(-8px)' },
        },
      },
      animation: {
        'fade-in-up': 'fade-in-up 0.6s ease-out',
        'fade-in-scale': 'fade-in-scale 0.5s ease-out',
        'glow-pulse': 'glow-pulse 3s ease-in-out infinite',
        'float-gentle': 'float-gentle 4s ease-in-out infinite',
      },
    },
  },
  plugins: [],
};