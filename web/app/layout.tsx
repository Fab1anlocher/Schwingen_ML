import type { Metadata } from "next";
import Link from "next/link";
import { Fraunces, Inter } from "next/font/google";
import "./globals.css";
import { NavLinks } from "@/components/NavLinks";
import { TeilenButton } from "@/components/TeilenButton";

const display = Fraunces({
  subsets: ["latin"],
  weight: ["400", "600", "700"],
  style: ["normal", "italic"],
  variable: "--font-display",
  display: "swap",
});

const sans = Inter({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Schwingen ML — Gang-Prognose",
  description:
    "Datengetriebene, erklärbare Prognose für Schwingen-Gänge. Informativ, kein Wettangebot.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="de" className={`${display.variable} ${sans.variable}`}>
      <body>
        <header className="header">
          <div className="header-inner">
            <Link href="/" className="brand">
              <span className="brand-mark" aria-hidden />
              Schwingen<span className="brand-accent">ML</span>
            </Link>
            <div className="header-rechts">
              <NavLinks />
              <TeilenButton />
            </div>
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
