import type { Metadata } from "next";
import "./globals.css";
import AuthGate from "@/components/AuthGate";
import { SeasonProvider } from "@/components/SeasonContext";

export const metadata: Metadata = {
  title: "ScoutIQ — Recruitment Intelligence",
  description: "Player scouting, role fit, valuation, risk, and squad building.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="font-sans antialiased">
        <SeasonProvider>
          <AuthGate>{children}</AuthGate>
        </SeasonProvider>
      </body>
    </html>
  );
}
