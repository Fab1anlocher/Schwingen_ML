"""Validier-Sonde: schlussgang.ch statistic-final.pdf parsen (aus GitHub Actions)."""
from __future__ import annotations

import io
import urllib.request

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/124.0.0.0 Safari/537.36")
PDF_URL = ("https://backend-api.schlussgang.ch/sites/default/files/"
           "event-ranking-list/52026-statistic-final.pdf")


def _get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=45) as resp:
        return resp.read()


def main():
    from pipeline.scrape.schlussgang_pdf import parse_statistic_pdf
    from pipeline.labels import dedupliziere

    data = _get(PDF_URL)
    print(f"PDF geladen: {len(data)} Bytes")

    import pdfplumber
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        print("--- Seite 1, erste 12 Zeilen (Titel/Datum) ---")
        for line in (pdf.pages[0].extract_text() or "").splitlines()[:12]:
            print(f"  | {line}")

    schwinger, roh = parse_statistic_pdf(data, "52026", "2026-04-06", "regional")
    print(f"\nGeparst: {len(schwinger)} Schwinger, {len(roh)} Roh-Gang-Einträge")
    gaenge, warnungen = dedupliziere(roh)
    print(f"Dedupliziert: {len(gaenge)} Gänge, {len(warnungen)} Warnungen")
    print("--- 12 Beispiel-Gänge ---")
    for g in gaenge[:12]:
        a = g.schwinger_a_id.split("|")[0]
        b = g.schwinger_b_id.split("|")[0]
        print(f"  {a} vs {b}: {g.ergebnis}  (Noten {g.note_a}/{g.note_b})")
    print("--- 5 Warnungen ---")
    for w in warnungen[:5]:
        print(f"  {w}")
    # Verteilung der Ergebnisse (Plausibilität).
    from collections import Counter
    print("Ergebnis-Verteilung:", Counter(g.ergebnis for g in gaenge))


if __name__ == "__main__":
    main()
