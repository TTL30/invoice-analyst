import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          DEFAULT: "#008080",
          light: "#32a8a8",
          dark: "#005f5f",
        },
      },
      boxShadow: {
        card: "0 2px 12px rgba(0,0,0,0.10)",
      },
    },
  },
  plugins: [],
};

export default config;
