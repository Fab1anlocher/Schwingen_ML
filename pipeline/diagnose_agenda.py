"""Diagnose für die Vorschau "kommende Feste" (FR-2).

Beantwortet auf einer Maschine MIT Netzzugang zu schlussgang.ch in einem Lauf,
warum die Vorschau leer bleibt. Die Stufen sind bewusst einzeln ausgewiesen,
weil sie unterschiedliche Reparaturen nach sich ziehen:

    python -m pipeline.diagnose_agenda

1. robots.txt erreichbar?      -> nein: ``hole()`` blockt ALLES still ab,
                                  weil ein RobotFileParser ohne gelesene
                                  robots.txt jede URL verbietet.
2. robots erlaubt die URL?     -> nein: Quelle darf nicht abgerufen werden.
3. JSON:API liefert Feste?     -> ja: Primärpfad ist gesund.
4. Agenda-HTML mit JSON-LD?    -> Fallback-Pfad; zeigt an, ob das Markup
                                  überhaupt noch Event-Blöcke enthält.
"""
from __future__ import annotations

import json
from datetime import date, timedelta

from .scrape import agenda as A
from .scrape.http import darf_abrufen, hole


def _stufe(nr: int, titel: str) -> None:
    print(f"\n[{nr}] {titel}")


def main() -> int:
    heute = date.today()
    print(f"Diagnose 'kommende Feste' — heute {heute.isoformat()}")

    for nr, url in ((1, A.EVENT_LIST_URL), (2, A.AGENDA_URL)):
        _stufe(nr, f"robots.txt-Prüfung für {url}")
        try:
            erlaubt = darf_abrufen(url)
        except Exception as e:  # noqa: BLE001
            print(f"    FEHLER: {type(e).__name__}: {e}")
            continue
        print(f"    darf_abrufen = {erlaubt}")
        if not erlaubt:
            print("    -> Entweder verbietet robots.txt diesen Pfad, ODER robots.txt war")
            print("       nicht abrufbar. Beides endet in hole() als PermissionError.")

    _stufe(3, "JSON:API (Primärpfad)")
    bis = (heute + timedelta(days=A.HORIZONT_TAGE)).isoformat()
    url = A.kommende_url(0, 50, ab_datum=heute.isoformat(), bis_datum=bis, typ="Aktivschwinger")
    print(f"    URL: {url}")
    try:
        roh = json.loads(hole(url))
        feste = A.parse_jsonapi_kommende(roh, heute=heute)
        print(f"    Roh-Einträge: {len(roh.get('data') or [])} -> kommende Feste: {len(feste)}")
        for f in feste[:10]:
            print(f"      {f['datum']}  {f['typ']:<14} {f['name']}")
    except Exception as e:  # noqa: BLE001
        print(f"    FEHLER: {type(e).__name__}: {e}")

    _stufe(4, "Agenda-HTML (Fallback)")
    try:
        html = hole(A.AGENDA_URL)
        bloecke = A._extract_jsonld(html)
        events = A.parse_agenda_html(html, heute=heute)
        print(f"    HTML {len(html)} Zeichen, JSON-LD-Blöcke: {len(bloecke)}, "
              f"davon Event+zukünftig: {len(events)}")
        if bloecke and not events:
            typen = sorted({str(b.get('@type')) for b in bloecke})
            print(f"    JSON-LD vorhanden, aber keine kommenden Events. @type-Werte: {typen}")
        if not bloecke:
            print("    Kein JSON-LD im Markup -> Parser muss neu kalibriert werden "
                  "(oder die Seite rendert clientseitig).")
    except Exception as e:  # noqa: BLE001
        print(f"    FEHLER: {type(e).__name__}: {e}")

    _stufe(5, "Gesamtergebnis (so wie die Pipeline es sieht)")
    feste, diagnose = A.lade_kommende(heute=heute)
    print(f"    {len(feste)} Feste, Pfad={diagnose.get('pfad')}")
    for v in diagnose.get("versuche", []):
        print(f"      {v}")
    return 0 if feste else 1


if __name__ == "__main__":
    raise SystemExit(main())
