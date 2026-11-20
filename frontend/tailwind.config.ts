import type { Config } from "tailwindcss";
const config: Config = {
  darkMode: "class",
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        background: "hsl(var(--background))", foreground: "hsl(var(--foreground))",
        card: "hsl(var(--card))", muted: "hsl(var(--muted))", "muted-foreground": "hsl(var(--muted-foreground))",
        border: "hsl(var(--border))", input: "hsl(var(--input))", primary: "hsl(var(--primary))", "primary-foreground": "hsl(var(--primary-foreground))",
        accent: "hsl(var(--accent))", cyan: "hsl(var(--cyan))", success: "hsl(var(--success))", warning: "hsl(var(--warning))", danger: "hsl(var(--danger))",
      },
      borderRadius: { lg: "0.85rem", md: "0.6rem", sm: "0.4rem", xl: "1.1rem" },
      keyframes: {
        fadeUp: { "0%": { opacity: "0", transform: "translateY(10px)" }, "100%": { opacity: "1", transform: "translateY(0)" } },
        shimmer: { "0%": { transform: "translateX(-100%)" }, "100%": { transform: "translateX(100%)" } },
        floaty: { "0%,100%": { transform: "translateY(0)" }, "50%": { transform: "translateY(-6px)" } },
      },
      animation: { "fade-up": "fadeUp .45s cubic-bezier(.2,.7,.2,1) both", shimmer: "shimmer 1.8s infinite", floaty: "floaty 5s ease-in-out infinite" },
    },
  },
  plugins: [],
};
export default config;
