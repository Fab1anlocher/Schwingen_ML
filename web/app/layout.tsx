import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Schwingen Gang-Prognose",
  description:
    "Datengetriebene, erklärbare Prognose für Schwingen-Gänge. Informativ, kein Wettangebot.",
};

const NAV = [
  { href: "/", label: "Paar-Prognose" },
  { href: "/feste", label: "Feste" },
  { href: "/schwinger", label: "Schwinger" },
  { href: "/analyse", label: "Analyse" },
];

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="de">
      <body>
        <header className="header">
          <div className="header-inner">
            <Link href="/" className="brand">
              🤼 Schwingen<span className="brand-accent">ML</span>
            </Link>
            <nav className="nav">
              {NAV.map((n) => (
                <Link key={n.href} href={n.href}>
                  {n.label}
                </Link>
              ))}
            </nav>
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
