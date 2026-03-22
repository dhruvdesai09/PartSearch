/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#f0f9ff",
          100: "#e0f2fe",
          200: "#bae6fd",
          300: "#7dd3fc",
          400: "#38bdf8",
          500: "#0ea5e9",
          600: "#0284c7",
          700: "#0369a1",
        },
        accent: {
          violet: "#7c3aed",
          mint: "#14b8a6",
          coral: "#fb923c",
        },
      },
      boxShadow: {
        brand: "0 4px 24px -4px rgba(14, 165, 233, 0.25)",
        card: "0 8px 32px -8px rgba(15, 23, 42, 0.08), 0 0 0 1px rgba(15, 23, 42, 0.04)",
        glow: "0 0 40px -8px rgba(124, 58, 237, 0.35)",
      },
      keyframes: {
        "fade-in-up": {
          "0%": { opacity: "0", transform: "translateY(6px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        "fade-in": {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        "load-bar": {
          "0%": { transform: "translateX(-100%)" },
          "100%": { transform: "translateX(400%)" },
        },
        "pulse-ring": {
          "0%, 100%": { boxShadow: "0 0 0 0 rgba(20, 184, 166, 0.45)" },
          "50%": { boxShadow: "0 0 0 10px rgba(20, 184, 166, 0)" },
        },
      },
      animation: {
        "fade-in-up": "fade-in-up 0.35s ease-out forwards",
        "fade-in": "fade-in 0.2s ease-out forwards",
        "pulse-ring": "pulse-ring 1.5s ease-out infinite",
        "load-bar": "load-bar 1.2s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
