"""Kalibrier-Sonde für schlussgang.ch (aus GitHub Actions).

schlussgang.ch ist vom Cloud-Runner erreichbar (kein WAF gegen Rechenzentrums-
IPs). Diese Sonde dumpt:
  1. den extrahierten Text einer statistic-final.pdf (Gang-Statistik, §4.1),
  2. relevante Links der /resultate-Seite (Event-Discovery),
damit der PDF-Parser + die Event-Auflösung exakt gebaut werden können.
Tolerant (exit 0).
"""
from __future__ import annotations

import io
import re
import urllib.request
import urllib.error

UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
PDF_URL = ("https://backend-api.schlussgang.ch/sites/default/files/"
           "event-ranking-list/52026-statistic-final.pdf")
RESULTATE_URL = "https://www.schlussgang.ch/resultate"


def _get(url: str, binaer: bool = False):
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/pdf,*/*;q=0.8",
        "Accept-Language": "de-CH,de;q=0.9",
    })
    with urllib.request.urlopen(req, timeout=45) as resp:
        return resp.read()


def dump_pdf():
    print("=== PDF-Text: statistic-final.pdf ===")
    try:
        import pdfplumber  # type: ignore
    except ImportError:
        print("  pdfplumber fehlt"); return
    try:
        data = _get(PDF_URL, binaer=True)
    except Exception as e:  # noqa: BLE001
        print(f"  Download-Fehler: {e}"); return
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        print(f"  Seiten: {len(pdf.pages)}")
        for pi, page in enumerate(pdf.pages[:2]):
            print(f"\n--- Seite {pi+1}: TEXT ---")
            txt = page.extract_text() or ""
            for line in txt.splitlines()[:70]:
                print(f"  | {line}")
            tables = page.extract_tables()
            print(f"\n--- Seite {pi+1}: {len(tables)} Tabelle(n) ---")
            for ti, tb in enumerate(tables[:1]):
                for row in tb[:8]:
                    print(f"  T{ti}| {row}")


def dump_resultate():
    print("\n=== /resultate: Event-/PDF-Links ===")
    try:
        html = _get(RESULTATE_URL).decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001
        print(f"  Fehler: {e}"); return
    hrefs = re.findall(r'href="([^"]+)"', html)
    rel = [h for h in hrefs if re.search(r"event|statistic|ranking|-final|anlass|\.pdf", h, re.I)]
    for h in list(dict.fromkeys(rel))[:30]:
        print(f"  {h}")
    # IDs im HTML (Event-/Anlass-IDs, statistic-URLs)
    ids = re.findall(r"event-ranking-list/(\d+)-", html)
    print(f"  Gefundene Ranking-IDs: {sorted(set(ids))[:20]}")


def main():
    dump_pdf()
    dump_resultate()


if __name__ == "__main__":
    main()
