import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  darkMode: "media",
  theme: {
    extend: {
      colors: {
        brand: {
          DEFAULT: "#0d6e6e",
          dark: "#0a5252",
        },
        surface: {
          DEFAULT: "#ffffff",
          dark: "#0f172a",
        },
        border: {
          DEFAULT: "#e2e8f0",
          dark: "#1e293b",
        },
        muted: {
          DEFAULT: "#64748b",
          dark: "#94a3b8",
        },
        danger: {
          DEFAULT: "#b45309",
          bg: "#fffbeb",
          border: "#fcd34d",
        },
      },
    },
  },
  plugins: [],
};

export default config;
