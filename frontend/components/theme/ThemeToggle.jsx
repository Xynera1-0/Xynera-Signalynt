"use client";

import { MoonStar, SunMedium } from "lucide-react";
import { useTheme } from "./ThemeProvider";

export default function ThemeToggle() {
  const { ready, isDark, toggleTheme } = useTheme();

  return (
    <button type="button" className="btn-ghost" onClick={toggleTheme} disabled={!ready}>
      {isDark ? <SunMedium className="h-4 w-4" /> : <MoonStar className="h-4 w-4" />}
      {isDark ? "Light mode" : "Dark mode"}
    </button>
  );
}
