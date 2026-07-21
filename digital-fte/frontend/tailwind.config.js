/** Design tokens live here and in globals.css — never as ad-hoc hex in a component.
 *  The app keeps its dark identity; this sharpens it rather than replacing it. */
module.exports = {
  content: ["./app/**/*.{js,jsx}", "./components/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        // One accent, committed to. Everything interactive is `accent`.
        accent: {
          soft: "#1e2140",
          400: "#8b9dff",
          500: "#6d8bff",
          600: "#5570f0",
          700: "#3f55d4",
        },
        // Indigo-tinted neutrals — cooler and more deliberate than flat gray.
        base: {
          900: "#0b0d15",   // page
          800: "#12141f",   // panel
          700: "#181b28",   // raised panel
          600: "#1f2333",   // hover
          line: "#282d3d",
        },
        ink: {
          DEFAULT: "#e8eaf2",
          muted: "#9aa2b8",
          faint: "#6f7689",
        },
        // Semantic priority — tuned to read on dark without vibrating.
        high: { bg: "#2a1417", fg: "#ff8f8f", line: "#5c2429" },
        normal: { bg: "#0f2a1d", fg: "#6ee7a8", line: "#1e4a35" },
        low: { bg: "#1a1e2b", fg: "#9aa2b8", line: "#282d3d" },
      },
      borderRadius: {
        // One radius scale. `xl` is the default for every surface.
        xl: "0.875rem",
        "2xl": "1.25rem",
      },
      boxShadow: {
        card: "0 1px 2px rgba(0,0,0,.3), 0 12px 32px -16px rgba(0,0,0,.65)",
        lift: "0 8px 28px -12px rgba(109,139,255,.55)",
      },
      fontFamily: {
        sans: ["ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "Roboto",
               "Helvetica Neue", "Arial", "sans-serif"],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "Consolas", "monospace"],
      },
      keyframes: {
        "fade-up": {
          from: { opacity: 0, transform: "translateY(4px)" },
          to: { opacity: 1, transform: "translateY(0)" },
        },
        blink: { "0%,80%,100%": { opacity: 0.2 }, "40%": { opacity: 1 } },
      },
      animation: {
        "fade-up": "fade-up .18s ease-out both",
        blink: "blink 1.4s infinite",
      },
    },
  },
  plugins: [],
};
