import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";
import { NavLinks } from "@/components/NavLinks";

export const metadata: Metadata = {
  title: "Schwingen Gang-Prognose",
  description:
    "Datengetriebene, erklärbare Prognose für Schwingen-Gänge. Informativ, kein Wettangebot.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="de">
      <body>
        <header className="header">
          <div className="header-inner">
            <Link href="/" className="brand">
              🤼 Schwingen<span className="brand-accent">ML</span>
            </Link>
            <NavLinks />
          </div>
        </header>
        <main className="main">{children}</main>
        <footer className="footer">
          <p>
            Prognosen sind informativ und <strong>kein Wettangebot</strong>. Datenquellen:
            schlussgang.ch u. a. · Nicht-kommerzielles Hobby-Projekt.
          </p>
        </footer>
      </body>
    </html>
  );
}
