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
        pop: { "0%": { opacity: "0", transform: "scale(.3)" }, "60%": { opacity: "1", transform: "scale(1.25)" }, "100%": { transform: "scale(1)" } },
        slideIn: { "0%": { opacity: "0", transform: "translateX(-8px)" }, "100%": { opacity: "1", transform: "translateX(0)" } },
      },
      animation: { "fade-up": "fadeUp .45s cubic-bezier(.2,.7,.2,1) both", shimmer: "shimmer 1.8s infinite", floaty: "floaty 5s ease-in-out infinite", pop: "pop .4s cubic-bezier(.2,.9,.3,1.4) both", "slide-in": "slideIn .35s ease both" },
    },
  },
  plugins: [],
};
export default config;
