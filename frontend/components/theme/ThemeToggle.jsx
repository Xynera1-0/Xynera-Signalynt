"use client";

import { MoonStar, SunMedium } from "lucide-react";
import { useTheme } from "./ThemeProvider";

export default function ThemeToggle() {
  const { ready, isDark, toggleTheme } = useTheme();

  return (
    <button
      type="button"
      className="btn-ghost h-10 w-10 p-0"
      onClick={toggleTheme}
      disabled={!ready}
      aria-label="Toggle theme"
      title="Toggle theme"
    >
      {isDark ? <SunMedium className="h-4 w-4" /> : <MoonStar className="h-4 w-4" />}
    </button>
  );
}
