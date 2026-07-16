/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#EDF5F1",
          100: "#D3E7DD",
          200: "#A8D0BC",
          300: "#78B69A",
          400: "#4B9C79",
          500: "#2F7D5D",
          600: "#1F5D46",
          700: "#194A38",
          800: "#143A2C",
          900: "#0F2C21",
        },
        ink: {
          50: "#F5F6F5",
          100: "#E7E9E7",
          200: "#CBD0CC",
          300: "#A3ABA5",
          400: "#75817A",
          500: "#57645D",
          600: "#414D46",
          700: "#333D37",
          800: "#242C27",
          900: "#171D19",
          950: "#0D1210",
        },
        amber: {
          50: "#FBF3E7",
          500: "#C2760C",
          600: "#9C5E09",
        },
        rust: {
          50: "#FBEAE7",
          500: "#B3402C",
          600: "#912F1E",
        },
      },
      fontFamily: {
        display: ["Manrope", "system-ui", "sans-serif"],
        body: ["'IBM Plex Sans'", "system-ui", "sans-serif"],
        mono: ["'IBM Plex Mono'", "ui-monospace", "monospace"],
      },
      boxShadow: {
        card: "0 1px 2px rgba(13, 18, 16, 0.06), 0 1px 3px rgba(13, 18, 16, 0.08)",
      },
      borderRadius: {
        card: "10px",
      },
    },
  },
  plugins: [],
};
