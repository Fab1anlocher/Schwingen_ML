"""Test des automatischen Fest-Finders (discover.liste_feste)."""
from __future__ import annotations


def main():
    from pipeline.scrape.discover import liste_feste
    feste = liste_feste(max_feste=25)
    print(f"Gefundene Feste mit Statistik-PDF: {len(feste)}")
    for f in feste[:20]:
        print(f"  {f['datum']} | {f['typ']:<14} | esv={f['esv_id']} | {f['name'][:40]}")
        print(f"      {f['pdf_url']}")
    # Datumsspanne (für zeitlichen Holdout wichtig)
    daten = sorted({f["datum"][:4] for f in feste if f.get("datum")})
    print("Saisons abgedeckt:", daten)


if __name__ == "__main__":
    main()
