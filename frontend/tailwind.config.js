/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: [
          "Segoe UI", "system-ui", "-apple-system", "Roboto", "Ubuntu",
          "Cantarell", "Noto Sans", "sans-serif", "Helvetica", "Arial",
        ],
      },
      keyframes: {
        progress: {
          "0%": { transform: "translateX(-120%)" },
          "100%": { transform: "translateX(420%)" },
        },
      },
      animation: {
        progress: "progress 1.3s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
