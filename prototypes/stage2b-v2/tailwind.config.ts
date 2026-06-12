import type { Config } from "tailwindcss";

export default {
  darkMode: ["class"],
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ember: {
          50: "#fff6df",
          100: "#f5dfaa",
          300: "#d9a64f",
          500: "#a96f2e",
          700: "#644226",
          900: "#221611"
        },
        iron: {
          50: "#eef4f4",
          200: "#a9b8b6",
          500: "#536565",
          800: "#1c2929",
          950: "#091010"
        },
        night: {
          900: "#11100e",
          950: "#080706"
        },
        arcane: {
          300: "#a99aff",
          500: "#7768c9",
          800: "#262448"
        }
      },
      boxShadow: {
        brass: "0 0 0 1px rgba(214, 169, 87, .36), inset 0 1px 0 rgba(255,255,255,.08), 0 22px 80px rgba(0,0,0,.38)",
        insetDeep: "inset 0 0 24px rgba(0,0,0,.6)"
      },
      fontFamily: {
        ui: ["Inter", "Segoe UI", "system-ui", "sans-serif"],
        display: ["Georgia", "Times New Roman", "serif"]
      }
    }
  },
  plugins: [require("tailwindcss-animate")]
} satisfies Config;
