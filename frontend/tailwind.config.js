/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/**/*.{js,jsx,ts,tsx}",
    "./components/**/*.{js,jsx,ts,tsx}",
    "./lib/**/*.{js,jsx,ts,tsx}",
  ],
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
      },
      fontFamily: {
        sans: ["Sora", "Manrope", "ui-sans-serif", "system-ui", "sans-serif"],
      },
      boxShadow: {
        glow: "0 0 0 1px rgba(68, 205, 224, 0.3), 0 12px 48px rgba(68, 205, 224, 0.12)",
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
