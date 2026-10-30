/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#F0F9FF",
          100: "#E0F2FE",
          200: "#BAE6FD",
          300: "#7DD3FC",
          400: "#38BDF8",
          500: "#0EA5E9",
          600: "#0284C7",
          700: "#0369A1",
          800: "#075985",
          900: "#0C4A6E",
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
        "card-hover": "0 2px 4px rgba(13, 18, 16, 0.07), 0 8px 16px -4px rgba(13, 18, 16, 0.10)",
        floating: "0 4px 6px rgba(13, 18, 16, 0.05), 0 12px 28px -6px rgba(13, 18, 16, 0.16)",
        "focus-brand": "0 0 0 3px rgba(14, 165, 233, 0.25)",
      },
      borderRadius: {
        card: "10px",
      },
      transitionTimingFunction: {
        "out-expo": "cubic-bezier(0.16, 1, 0.3, 1)",
      },
      keyframes: {
        "fade-in": { "0%": { opacity: "0" }, "100%": { opacity: "1" } },
        "fade-in-up": { "0%": { opacity: "0", transform: "translateY(6px)" }, "100%": { opacity: "1", transform: "translateY(0)" } },
        "scale-in": { "0%": { opacity: "0", transform: "scale(0.96)" }, "100%": { opacity: "1", transform: "scale(1)" } },
        "slide-in-right": { "0%": { opacity: "0", transform: "translateX(12px)" }, "100%": { opacity: "1", transform: "translateX(0)" } },
        shimmer: { "0%": { backgroundPosition: "-468px 0" }, "100%": { backgroundPosition: "468px 0" } },
      },
      animation: {
        "fade-in": "fade-in 0.2s ease-out",
        "fade-in-up": "fade-in-up 0.25s ease-out",
        "scale-in": "scale-in 0.15s ease-out",
        "slide-in-right": "slide-in-right 0.2s ease-out",
        shimmer: "shimmer 1.6s linear infinite",
      },
    },
  },
  plugins: [],
};
