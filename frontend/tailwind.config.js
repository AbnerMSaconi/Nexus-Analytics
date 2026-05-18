/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        ucdb: {
          blue: '#003366',
          blueHover: '#002852',
          red: '#990000',
        }
      }
    },
  },
  plugins: [require('@tailwindcss/typography')],
}