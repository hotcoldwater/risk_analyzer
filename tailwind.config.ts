import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        ink: "#102033",
        mist: "#edf4fb",
        line: "#d0ddeb",
        accent: "#0f7a95",
        accentSoft: "#d4f0f6",
        warn: "#b45309",
        danger: "#b42318"
      },
      boxShadow: {
        panel: "0 14px 34px rgba(16, 32, 51, 0.08)"
      }
    }
  },
  plugins: []
};

export default config;
