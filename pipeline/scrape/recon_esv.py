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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--anlass", help="Konkrete Anlass-ID (sonst erste von der Indexseite)")
    ap.add_argument("--out", default=str(ROOT / "recon"), help="Zielordner für HTML-Dumps")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    print(f"[1/3] Index laden: {ESV_BASE}")
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
