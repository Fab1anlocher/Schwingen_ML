"""Recon-/Kalibrierhilfe für die ESV-Ranglisten.

Diese Umgebung kann esv.ch nicht erreichen (Egress-Sperre). Führe dieses
Skript dort aus, wo das Internet offen ist (dein Rechner oder GitHub Actions),
um eine echte Seite abzugreifen. Es:
  1. lädt die Index-Seite und extrahiert Anlass-IDs,
  2. lädt eine Beispiel-Rangliste und speichert das rohe HTML,
  3. zeigt, wie der aktuelle Parser (esv.py) die Seite interpretiert.

So sehen wir das echte Layout und können esv.parse_rangliste final kalibrieren.

Aufruf:
    python -m pipeline.scrape.recon_esv                 # Index + erster Anlass
    python -m pipeline.scrape.recon_esv --anlass 3694   # bestimmter Anlass
"""
from __future__ import annotations

import argparse
from pathlib import Path

from ..config import ESV_BASE, ROOT
from .http import hole
from . import esv


def _diagnose(html: str) -> None:
    """Druckt die reale Seitenstruktur in die Logs (Parser-Kalibrierung)."""
    try:
        from bs4 import BeautifulSoup  # type: ignore
    except ImportError:
        print("      (bs4 fehlt — Diagnose übersprungen)")
        return
    soup = BeautifulSoup(html, "html.parser")
    tabellen = soup.find_all("table")
    print(f"      Diagnose: {len(tabellen)} <table>-Elemente")
    if not tabellen:
        # Möglicher Hinweis auf JS-gerenderte SPA.
        n_script = len(soup.find_all("script"))
        print(f"      ⚠ Keine Tabelle im HTML. {n_script} <script>-Tags — evtl. JS-gerendert.")
        print("        In diesem Fall ist ein Headless-Browser (Playwright) nötig.")
        # Sichtbare Textstruktur andeuten.
        txt = soup.get_text("\n", strip=True)
        print("      --- erste 40 sichtbare Textzeilen ---")
        for line in txt.splitlines()[:40]:
            print(f"        | {line[:120]}")
        return
    tabelle = max(tabellen, key=lambda t: len(t.find_all("tr")))
    zeilen = tabelle.find_all("tr")
    print(f"      Grösste Tabelle: {len(zeilen)} Zeilen")
    print("      --- erste 6 Zeilen (Zellen-Text) ---")
    for tr in zeilen[:6]:
        zellen = [td.get_text(" ", strip=True) for td in tr.find_all(["td", "th"])]
        print(f"        | {zellen}")


def _probe(url: str, out: Path) -> bool:
    """Testet einen Endpunkt tolerant und protokolliert das Ergebnis."""
    import urllib.error
    print(f"\n>>> PROBE {url}")
    try:
        html = hole(url)
    except urllib.error.HTTPError as e:
        print(f"    HTTP {e.code} {e.reason}  (Bot-/WAF-Sperre wahrscheinlich)")
        return False
    except Exception as e:  # noqa: BLE001
        print(f"    Fehler: {type(e).__name__}: {e}")
        return False
    name = url.replace("https://", "").replace("/", "_").replace("?", "_")[:60]
    (out / f"{name}.html").write_text(html, encoding="utf-8")
    print(f"    OK  {len(html)} Zeichen  -> {name}.html")
    _diagnose(html)
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--anlass", default="3694", help="Anlass-ID (Default 3694 = ESAF 2025)")
    ap.add_argument("--out", default=str(ROOT / "recon"), help="Zielordner für HTML-Dumps")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    # Diagnose: Welche esv.ch-Endpunkte sind von hier erreichbar?
    print("=== ERREICHBARKEITS-DIAGNOSE esv.ch ===")
    ziele = [
        "https://esv.ch/",
        ESV_BASE,
        f"{ESV_BASE}?anlass={args.anlass}",
        f"https://isv.esv.ch/ranglisten/?anlass={args.anlass}",
    ]
    erreichbar = [z for z in ziele if _probe(z, out)]
    print(f"\n=== Ergebnis: {len(erreichbar)}/{len(ziele)} Endpunkte erreichbar ===")
    if not erreichbar:
        print("KEIN Endpunkt erreichbar — esv.ch blockt diese IP (WAF/Cloudflare).")
        print("→ Von einer Wohn-IP (Heimrechner) erneut versuchen, ggf. mit Playwright.")
        return
    # Falls erreichbar: die Rangliste regulär durchparsen.
    print("\n[Parser] Rangliste interpretieren ...")
    index_html = hole(ESV_BASE)
    (out / "index.html").write_text(index_html, encoding="utf-8")
    ids = esv.finde_anlass_ids(index_html)
    print(f"      {len(ids)} Anlass-IDs gefunden: {ids[:15]}{' …' if len(ids) > 15 else ''}")

    aid = args.anlass or (ids[0] if ids else None)
    if not aid:
        print("      Keine Anlass-ID gefunden — bitte --anlass <ID> angeben.")
        print(f"      index.html wurde gespeichert in {out}/index.html — schick sie mir.")
        return

    url = esv.anlass_url(aid)
    print(f"[2/3] Rangliste laden: {url}")
    html = hole(url)
    dump = out / f"anlass_{aid}.html"
    dump.write_text(html, encoding="utf-8")
    print(f"      HTML gespeichert: {dump}  ({len(html)} Zeichen)")

    # --- Diagnose: Struktur der echten Seite (für Parser-Kalibrierung) ---
    _diagnose(html)

    print(f"[3/3] Aktueller Parser interpretiert die Seite so:")
    try:
        schwinger, event, roh = esv.parse_rangliste(html, str(aid))
        print(f"      Event : {event.name} | {event.datum} | Typ={event.typ}")
        print(f"      Schwinger: {len(schwinger)}  |  Roh-Gang-Einträge: {len(roh)}")
        for s in list(schwinger.values())[:5]:
            print(f"        - {s.name} (Jg {s.jahrgang}, {s.teilverband})")
        for r in roh[:5]:
            print(f"        Gang: {r.schwinger_id} vs {r.gegner_id}  {r.symbol}  Note={r.note}")
        if not roh:
            print("      ⚠ Keine Gang-Einträge geparst — Layout weicht ab.")
            print("        Bitte die gespeicherte HTML-Datei schicken, dann kalibriere ich den Parser.")
    except Exception as e:  # noqa: BLE001
        print(f"      Parser-Fehler: {e}")
        print(f"        Bitte {dump} schicken, dann kalibriere ich esv.parse_rangliste.")

    print(f"\nFertig. Schick mir am besten {out}/anlass_{aid}.html (und index.html),")
    print("dann passe ich den Parser exakt an das echte Layout an.")


if __name__ == "__main__":
    main()
