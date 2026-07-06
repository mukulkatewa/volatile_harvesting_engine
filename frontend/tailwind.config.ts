import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        "bg-deep":     "#080b10",
        "bg-panel":    "#11161d",
        "bg-card":     "#161d27",
        "bg-elevated": "#1c2430",
        "vhe-green":   "#00d09c",
        "vhe-red":     "#ff6b6b",
        "vhe-amber":   "#f0b429",
        "vhe-blue":    "#387ed1",
        "text-primary":"#e8edf4",
        "text-muted":  "#8b97a8",
        "text-faint":  "#5c6778",
      },
      fontFamily: {
        mono: ['"IBM Plex Mono"', "ui-monospace", "monospace"],
        sans: ['"IBM Plex Sans"', "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
} satisfies Config;
