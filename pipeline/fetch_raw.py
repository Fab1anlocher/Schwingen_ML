"""Kleines CLI zum Befüllen von artifacts/raw aus den Webquellen."""
from __future__ import annotations

import argparse
from pathlib import Path

from . import config
from .scrape.esv_statistiken import scrape_esv_statistiken, write_esv_stats_json
from .scrape.schlussgang_portraet import (
    scrape_schlussgang_portraets,
    write_schlussgang_raw_json,
)
from .scrape.schlussgang_resultate import (
    ergaenze_schwinger_stubs,
    merge_events_raw_json,
    merge_gaenge_raw_json,
    scrape_events_und_gaenge,
)

RAW_DIR = config.ARTIFACTS_DIR / "raw"


def _schwinger_path() -> Path:
    return RAW_DIR / "schwinger.json"


def _schlussgang_raw_path() -> Path:
    return RAW_DIR / "schlussgang_portraits.json"


def _esv_path() -> Path:
    return RAW_DIR / "esv_statistiken.json"


def _events_path() -> Path:
    return RAW_DIR / "events.json"


def _gaenge_path() -> Path:
    return RAW_DIR / "gaenge.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Lädt Rohdaten aus Schlussgang-Porträts und ESV-Statistiken."
    )
    parser.add_argument(
        "--sources",
        nargs="*",
        choices=["schlussgang", "esv", "events"],
        default=["schlussgang", "esv", "events"],
        help="Welche Quellen geholt werden sollen.",
    )
    parser.add_argument("--limit", type=int, default=None, help="Maximale Anzahl Porträts")
    parser.add_argument("--jahr", type=int, default=2026, help="ESV-Download-Jahr")
    parser.add_argument(
        "--download-pdfs",
        action="store_true",
        help="ESV-PDFs auch wirklich herunterladen und Text extrahieren.",
    )
    parser.add_argument(
        "--materialize-schwinger",
        action="store_true",
        help="Zusätzlich eine normalisierte schwinger.json aus den Porträts schreiben.",
    )
    parser.add_argument(
        "--event-limit", type=int, default=10, help="Maximale Anzahl Feste (Quelle 'events')."
    )
    parser.add_argument(
        "--seit-datum",
        default="2024-01-01",
        help="Nur Feste ab diesem Datum (Quelle 'events', ISO YYYY-MM-DD).",
    )
    parser.add_argument(
        "--fest-typ",
        default="Aktivschwinger",
        help="field_event_type-Filter (Quelle 'events'); leer = alle Kategorien.",
    )
    args = parser.parse_args(argv)

    RAW_DIR.mkdir(parents=True, exist_ok=True)

    if "schlussgang" in args.sources:
        profiles = scrape_schlussgang_portraets(max_profiles=args.limit)
        write_schlussgang_raw_json(_schlussgang_raw_path(), profiles)
        print(f"[schlussgang] {len(profiles)} Porträts gespeichert -> {_schlussgang_raw_path()}")
        if args.materialize_schwinger:
            from .scrape.schlussgang_portraet import write_schwinger_json

            write_schwinger_json(_schwinger_path(), profiles)
            print(f"[schlussgang] Normalisierte Schwinger geschrieben -> {_schwinger_path()}")

    if "esv" in args.sources:
        # esv.ch blockiert Anfragen von GitHub-Actions-Runnern (403, IP-basiert
        # -- funktioniert lokal problemlos), ausserhalb unserer Kontrolle.
        # esv_statistiken.json wird aktuell von keiner anderen Pipeline-Stufe
        # gelesen (nur schwinger/events/gaenge sind für --source scrape
        # nötig, s. pipeline/scrape/__init__.py:lade_echte_daten) -- ein
        # Fehlschlag hier darf daher NICHT die wichtigeren Quellen
        # (insb. "events", für NFR-1 tägliche Aktualität) verhindern.
        try:
            stats = scrape_esv_statistiken(jahr=args.jahr, download_pdfs=args.download_pdfs)
            write_esv_stats_json(_esv_path(), stats)
            print(f"[esv] {len(stats.get('downloads', []))} PDFs gespeichert -> {_esv_path()}")
        except Exception as e:  # noqa: BLE001
            print(f"[esv] übersprungen (Fehler beim Abruf, nicht kritisch): {e}")

    if "events" in args.sources:
        events, gaenge = scrape_events_und_gaenge(
            args.event_limit, seit_datum=args.seit_datum, typ=args.fest_typ
        )
        alle_events = merge_events_raw_json(_events_path(), events)
        alle_gaenge = merge_gaenge_raw_json(
            _gaenge_path(), gaenge, {e["id"] for e in events}
        )
        print(f"[events] {len(events)} Feste neu geladen, {len(alle_events)} total -> {_events_path()}")
        print(
            f"[events] {len(gaenge)} Roh-Gang-Einträge neu geladen, {len(alle_gaenge)} total "
            f"-> {_gaenge_path()}"
        )
        neu = ergaenze_schwinger_stubs(_schwinger_path(), gaenge)
        if neu:
            print(f"[events] {neu} Schwinger-Stubs ohne Porträt ergänzt -> {_schwinger_path()}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())