/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/**/*.{js,jsx,ts,tsx}",
    "./components/**/*.{js,jsx,ts,tsx}",
    "./lib/**/*.{js,jsx,ts,tsx}",
  ],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#eefeff",
          100: "#d5fdff",
          200: "#adf6fb",
          300: "#7be8f3",
          400: "#44cde0",
          500: "#28aec4",
          600: "#1f8ba7",
          700: "#1f6f87",
          800: "#205a6e",
          900: "#1f4b5d",
        },
        ember: {
          500: "#ff6f3c",
          600: "#eb5b2e",
        },
        // MD3 / Xynera design tokens
        "xyn-bg": "#0b1326",
        "xyn-surface": "#0b1326",
        "xyn-surface-low": "#131b2e",
        "xyn-surface-mid": "#171f33",
        "xyn-surface-high": "#222a3d",
        "xyn-surface-highest": "#2d3449",
        "xyn-on-surface": "#dae2fd",
        "xyn-primary": "#5deedd",
        "xyn-primary-container": "#36d1c1",
        "xyn-on-primary": "#003732",
        "xyn-outline": "#859491",
        "xyn-outline-variant": "#3c4947",
      },
      fontFamily: {
        sans: ["Inter", "Manrope", "ui-sans-serif", "system-ui", "sans-serif"],
        manrope: ["Manrope", "ui-sans-serif", "sans-serif"],
        inter: ["Inter", "ui-sans-serif", "sans-serif"],
      },
      boxShadow: {
        glow: "0 0 0 1px rgba(68, 205, 224, 0.3), 0 12px 48px rgba(68, 205, 224, 0.12)",
        "teal-sm": "0 4px 24px rgba(93, 238, 221, 0.12)",
      },
      animation: {
        "fade-in": "fadeIn 0.7s ease-out both",
        "slide-up": "slideUp 0.5s ease-out both",
      },
      keyframes: {
        fadeIn: {
          "0%": { opacity: "0" },
          "100%": { opacity: "1" },
        },
        slideUp: {
          "0%": { opacity: "0", transform: "translateY(12px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
      },
    },
  },
  plugins: [],
};
