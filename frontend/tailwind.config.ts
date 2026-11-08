import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: { DEFAULT: "#D7192A", dark: "#B01020" },
        ink: "#16181D",
        sand: "#F7F5F2",
      },
      fontFamily: {
        sans: ["'Plus Jakarta Sans Variable'", "'Noto Sans Devanagari'", "system-ui", "sans-serif"],
      },
      boxShadow: { soft: "0 1px 2px rgba(22,24,29,.04), 0 8px 24px rgba(22,24,29,.05)" },
    },
  },
  plugins: [],
};
export default config;
