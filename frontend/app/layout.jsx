import "./globals.css";
import AppProviders from "../components/providers/AppProviders";

export const metadata = {
  title: "Xynera Signal Workspace",
  description: "Ephemeral interfaces for market intelligence, content generation, and outreach orchestration.",
  icons: {
    icon: "/favicon.svg",
    shortcut: "/favicon.svg",
    apple: "/favicon.svg",
  },
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body>
        <AppProviders>{children}</AppProviders>
      </body>
    </html>
  );
}
