"use client";

// Navigation in der Kopfzeile; markiert die aktive Seite.

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV = [
  { href: "/", label: "Prognose" },
  { href: "/feste", label: "Feste" },
  { href: "/simulation", label: "Simulator" },
  { href: "/schwinger", label: "Schwinger" },
  { href: "/typen", label: "Typen" },
  { href: "/karte", label: "Karte" },
  { href: "/analyse", label: "Analyse" },
];

export function NavLinks() {
  const pathname = usePathname();
  return (
    <nav className="nav">
      {NAV.map((n) => (
        <Link key={n.href} href={n.href} className={pathname === n.href ? "nav-aktiv" : ""}>
          {n.label}
        </Link>
      ))}
    </nav>
  );
}
