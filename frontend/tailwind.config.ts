import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        base: "#0B0F14",
        panel: "#12171F",
        panelraised: "#161D27",
        border: "#1D2530",
        ink: "#E7ECF2",
        muted: "#8792A0",
        faint: "#5B6472",
        accent: "#D9A441",
        accentmuted: "#8A6B2E",
        risklow: "#4C9A6A",
        riskmed: "#D9A441",
        riskhigh: "#C1543D",
      },
      fontFamily: {
        sans: [
          "-apple-system", "BlinkMacSystemFont", "Segoe UI", "Inter", "Helvetica Neue", "Arial", "sans-serif",
        ],
        mono: [
          "ui-monospace", "SFMono-Regular", "SF Mono", "Menlo", "Consolas", "monospace",
        ],
      },
      fontSize: {
        "2xs": "0.6875rem",
      },
    },
  },
  plugins: [],
};
export default config;
