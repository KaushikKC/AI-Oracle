import type { Config } from "tailwindcss"

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        career:        "#6366f1",
        health:        "#10b981",
        finances:      "#f59e0b",
        relationships: "#ec4899",
        skills:        "#8b5cf6",
        other:         "#6b7280",
      },
    },
  },
  plugins: [],
}

export default config
