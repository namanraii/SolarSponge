/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./app/**/*.{js,ts,jsx,tsx}", "./components/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        paper: "#f3ead8",
        cream: "#faf6ee",
        sand: "#e6d7bf",
        clay: "#b8894a",
        gold: "#c48a1a",
        sun: "#e8a317",
        leaf: "#3d6b45",
        moss: "#2a4f32",
        sponge: "#3f8f7a",
        terracotta: "#c45c26",
        waste: "#c45c26",
        ink: "#1f1810",
        muted: "#6b5e4e",
        panel: "#fffaf2",
        pv: "#1e3a5f",
      },
      fontFamily: {
        display: ["Fraunces", "Georgia", "serif"],
        sans: ["Source Sans 3", "system-ui", "sans-serif"],
      },
      boxShadow: {
        card: "0 18px 40px -24px rgba(80, 52, 20, 0.35), 0 1px 0 rgba(255,255,255,0.7) inset",
        lift: "0 28px 60px -28px rgba(80, 52, 20, 0.45)",
      },
      backgroundImage: {
        grain:
          "url(\"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='160' height='160'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='4' stitchTiles='stitch'/><feColorMatrix values='0 0 0 0 0.55 0 0 0 0 0.48 0 0 0 0 0.36 0 0 0 0.18 0'/></filter><rect width='100%' height='100%' filter='url(%23n)'/></svg>\")",
      },
    },
  },
  plugins: [],
};
