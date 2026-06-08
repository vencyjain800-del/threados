import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      // Design system tokens — populated with brand identity in Sprint 4
      colors: {
        brand: {
          50: "#f0f4ff",
          100: "#e0eaff",
          500: "#3b5bdb",
          600: "#364fc7",
          700: "#2f44ad",
          900: "#1c2e78",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};

export default config;
