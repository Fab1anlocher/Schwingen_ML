"""CLI zum Befüllen von ``artifacts/raw`` aus den Webquellen (§4.1).

Ablauf:
  1. **Porträts** (schlussgang.ch JSON:API ``node/portrait``) -> Physis,
     Verband, Kranzstatus, bevorzugte Schwünge.
  2. **Feste + Gänge** (JSON:API ``node/event`` + Statistik-PDF je Fest)
     -> die eigentlichen Resultate.
  3. **Kader** aus 1 + 2 zustandslos neu bauen (``pipeline.roster``).

Schritt 3 ist bewusst kein inkrementelles Nachpflegen: der Kader ist eine
reine Funktion von Porträts + PDF-Namen. Vorher hing er am Stand des
CI-Caches und schwankte zwischen Läufen um Faktor 3, ohne dass sich an den
Quelldaten etwas geändert hatte.
"""
from __future__ import annotations

import argparse
import json
from datetime import date, timedelta
from pathlib import Path

from . import config
from .roster import baue_roster, pruefe_kader
from .scrape.schlussgang_portraet import (
    scrape_schlussgang_portraets,
    write_schlussgang_raw_json,
)
from .scrape.schlussgang_resultate import (
    merge_events_raw_json,
    merge_gaenge_raw_json,
    scrape_events_und_gaenge,
)

RAW_DIR = config.ARTIFACTS_DIR / "raw"


def _pfad(name: str) -> Path:
    return RAW_DIR / name


def _lade(name: str, schluessel: str) -> list[dict]:
    p = _pfad(name)
    if not p.exists():
        return []
    return json.loads(p.read_text(encoding="utf-8")).get(schluessel, [])


def bestimme_seit_datum(events: list[dict], *, rueckblick_tage: int = 14,
                        heute: date | None = None) -> str:
    """Startdatum für den inkrementellen Lauf aus den bereits geladenen Festen.

    Nimmt das jüngste bekannte Fest minus ``rueckblick_tage`` (Überlappung für
    Resultate, die erst später nachgetragen werden). Ohne bekannte Feste:
    30 Tage zurück -- der volle Neuaufbau läuft über ``--seit-datum``.

    Lag früher als Shell-Heredoc im Workflow-YAML und war damit weder testbar
    noch bei Fehlern sichtbar.
    """
    heute = heute or date.today()
    daten = sorted(str(e.get("datum") or "")[:10] for e in events if e.get("datum"))
    if not daten:
        return (heute - timedelta(days=30)).isoformat()
    try:
        juengstes = date.fromisoformat(daten[-1])
    except ValueError:
        return (heute - timedelta(days=30)).isoformat()
    return (juengstes - timedelta(days=rueckblick_tage)).isoformat()


def _schreibe_kader(portraits: list[dict], gaenge: list[dict]) -> dict:
    eintraege, statistik = baue_roster(portraits, gaenge)
    pfad = _pfad("schwinger.json")
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(
        json.dumps({"schwinger": eintraege}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    probleme = pruefe_kader(eintraege)
    print(
        f"[kader] {statistik['n_gesamt']} Schwinger "
        f"({statistik['n_portraits']} Porträts + {statistik['n_stubs']} nur-PDF), "
        f"{statistik['n_pdf_namen_auf_portraet_gemappt']} PDF-Namen einem Porträt zugeordnet "
        f"-> {pfad}"
    )
    if statistik["n_mehrdeutige_namen"]:
        print(
            f"[kader] {statistik['n_mehrdeutige_namen']} mehrdeutige Namen (nicht aufgelöst): "
            f"{statistik['mehrdeutige_namen'][:5]}"
        )
    for problem in probleme:
        print(f"[kader] WARNUNG: {problem}")
    return statistik


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Lädt Rohdaten von schlussgang.ch nach artifacts/raw."
    )
    parser.add_argument(
        "--sources",
        nargs="*",
        choices=["portraets", "events"],
        default=["portraets", "events"],
        help="Welche Quellen geholt werden sollen.",
    )
    parser.add_argument("--limit", type=int, default=None, help="Maximale Anzahl Porträts")
    parser.add_argument(
        "--event-limit", type=int, default=None, help="Maximale Anzahl Feste (Quelle 'events')."
    )
    parser.add_argument(
        "--seit-datum",
        default="auto",
        help="Nur Feste ab diesem Datum (ISO YYYY-MM-DD) oder 'auto' = ab dem "
             "jüngsten bereits geladenen Fest minus --rueckblick-tage.",
    )
    parser.add_argument(
        "--rueckblick-tage",
        type=int,
        default=14,
        help="Überlappung bei --seit-datum auto (fängt nachgetragene Resultate ein).",
    )
    parser.add_argument(
        "--fest-typ",
        default="Aktivschwinger",
        help="field_event_type-Filter (Quelle 'events'); leer = alle Kategorien.",
    )
    args = parser.parse_args(argv)

    RAW_DIR.mkdir(parents=True, exist_ok=True)

    if "portraets" in args.sources:
        portraits = scrape_schlussgang_portraets(max_profiles=args.limit)
        write_schlussgang_raw_json(_pfad("schlussgang_portraits.json"), portraits)
        print(f"[portraets] {len(portraits)} Porträts gespeichert")

    if "events" in args.sources:
        seit = args.seit_datum
        if seit == "auto":
            seit = bestimme_seit_datum(
                _lade("events.json", "events"), rueckblick_tage=args.rueckblick_tage
            )
            print(f"[events] inkrementell ab {seit} (auto)")
        events, gaenge = scrape_events_und_gaenge(
            args.event_limit, seit_datum=seit, typ=args.fest_typ
        )
        alle_events = merge_events_raw_json(_pfad("events.json"), events)
        bekannte = {str(e["id"]) for e in alle_events}
        alle_gaenge = merge_gaenge_raw_json(
            _pfad("gaenge.json"),
            gaenge,
            {e["id"] for e in events},
            bekannte_events=bekannte,
        )
        print(f"[events] {len(events)} Feste neu, {len(alle_events)} total")
        print(f"[events] {len(gaenge)} Roh-Gang-Einträge neu, {len(alle_gaenge)} total")

    # Kader IMMER neu bauen: er hängt an beiden Quellen und muss zum aktuellen
    # Stand von portraits + gaenge passen, egal welche davon gerade lief.
    _schreibe_kader(
        _lade("schlussgang_portraits.json", "profiles"),
        _lade("gaenge.json", "gaenge"),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
