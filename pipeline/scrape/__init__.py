"""Einlesen der gescrapten Rohdaten aus ``artifacts/raw`` (§4.1).

Die Scraper selbst schreiben nur nach ``artifacts/raw`` (s. ``pipeline.fetch_raw``);
hier werden diese Dateien auf das kanonische Schema (``pipeline.schema``)
abgebildet. Jeder verworfene Roh-Eintrag wird **gezählt und begründet** --
stiller Datenverlust war bisher die Hauptfehlerquelle: von 243'479 geladenen
Roh-Einträgen kamen nur 95'241 im Training an, ohne dass das irgendwo auffiel.
"""
from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from ..identity import baue_namensindex
from ..labels import RohGangEintrag
from ..schema import Event, Schwinger

RAW_DIR = Path(__file__).resolve().parent.parent.parent / "artifacts" / "raw"

# Feste stammen ausschliesslich aus der schlussgang.ch-JSON:API und tragen
# darum immer die ID "schlussgang-<nid>". Alles andere ist Alt-/Testdatenrest
# im additiven Roh-Cache (real gefunden: "ev-2026-test" -- "Testschwinget").
EVENT_ID_PRAEFIX = "schlussgang-"


@dataclass
class IngestBericht:
    """Buchhaltung über den Weg Rohdatei -> kanonische Objekte."""

    n_roh_gesamt: int = 0
    n_roh_uebernommen: int = 0
    verworfen: Counter = field(default_factory=Counter)
    n_events_gesamt: int = 0
    n_events_uebernommen: int = 0
    events_verworfen: Counter = field(default_factory=Counter)
    n_schwinger: int = 0
    n_namen_unaufloesbar: int = 0
    beispiele_unaufloesbar: list[str] = field(default_factory=list)

    @property
    def verlustquote(self) -> float:
        if not self.n_roh_gesamt:
            return 0.0
        return 1.0 - self.n_roh_uebernommen / self.n_roh_gesamt

    def als_dict(self) -> dict:
        return {
            "roh_eintraege_gelesen": self.n_roh_gesamt,
            "roh_eintraege_uebernommen": self.n_roh_uebernommen,
            "roh_eintraege_verworfen": dict(self.verworfen),
            "verlustquote": round(self.verlustquote, 4),
            "feste_gelesen": self.n_events_gesamt,
            "feste_uebernommen": self.n_events_uebernommen,
            "feste_verworfen": dict(self.events_verworfen),
            "schwinger_im_kader": self.n_schwinger,
            "unaufloesbare_namen": self.n_namen_unaufloesbar,
            "beispiele_unaufloesbare_namen": self.beispiele_unaufloesbar[:10],
        }


def _lade_raw_json(name: str, default):
    p = RAW_DIR / name
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))


def _lade_schwinger(raw_s: list[dict]) -> dict[str, Schwinger]:
    schwinger: dict[str, Schwinger] = {}
    for r in raw_s:
        name = str(r.get("name", "")).strip()
        sid = str(r.get("id") or "").strip()
        if not name or not sid:
            continue
        sw = r.get("bevorzugte_schwuenge") or r.get("schwuenge") or []
        schwinger[sid] = Schwinger(
            id=sid,
            name=name,
            jahrgang=r.get("jahrgang"),
            groesse_cm=r.get("groesse_cm"),
            gewicht_kg=r.get("gewicht_kg"),
            kranzstatus=str(r.get("kranzstatus", "kein")),
            teilverband=r.get("teilverband"),
            kanton=r.get("kanton"),
            schwingklub=r.get("schwingklub"),
            senne_turner=r.get("senne_turner"),
            bevorzugte_schwuenge=list(sw) if isinstance(sw, list) else [],
            quellen=list(r.get("quellen") or ["schlussgang.ch"]),
        )
    return schwinger


def _lade_events(raw_e: list[dict], bericht: IngestBericht) -> list[Event]:
    events: list[Event] = []
    bericht.n_events_gesamt = len(raw_e)
    for r in raw_e:
        eid = str(r.get("id") or "")
        if not eid or not r.get("datum") or not r.get("name"):
            bericht.events_verworfen["unvollstaendig"] += 1
            continue
        if not eid.startswith(EVENT_ID_PRAEFIX):
            # Kein Fest aus der offiziellen Quelle -> Testrest im Roh-Cache.
            bericht.events_verworfen["fremde_id"] += 1
            continue
        events.append(
            Event(
                id=eid,
                name=str(r["name"]),
                datum=str(r["datum"])[:10],
                typ=str(r.get("typ") or "regional"),
                ort=r.get("ort"),
                quelle=str(r.get("quelle") or "schlussgang.ch"),
            )
        )
    bericht.n_events_uebernommen = len(events)
    return events


def lade_echte_daten(*, mit_bericht: bool = False):
    """Lädt die gescrapten Rohdaten aus ``artifacts/raw``.

    Erwartete Dateien (alle von ``pipeline.fetch_raw`` erzeugt):
      - ``schwinger.json``: ``{"schwinger": [...]}``  (Porträts + PDF-Stubs)
      - ``events.json``:    ``{"events": [...]}``
      - ``gaenge.json``:    ``{"gaenge": [...]}``     (eine Zeile je PDF-Perspektive)
    """
    raw_s = _lade_raw_json("schwinger.json", {"schwinger": []}).get("schwinger", [])
    raw_e = _lade_raw_json("events.json", {"events": []}).get("events", [])
    raw_g = _lade_raw_json("gaenge.json", {"gaenge": []}).get("gaenge", [])

    bericht = IngestBericht()
    schwinger = _lade_schwinger(raw_s)
    bericht.n_schwinger = len(schwinger)
    events = _lade_events(raw_e, bericht)
    gueltige_events = {e.id for e in events}

    index = baue_namensindex(raw_s)
    unaufloesbar: Counter = Counter()

    roh: list[RohGangEintrag] = []
    bericht.n_roh_gesamt = len(raw_g)
    for r in raw_g:
        event_id = str(r.get("event_id") or "")
        if event_id not in gueltige_events:
            bericht.verworfen["fest_unbekannt_oder_verworfen"] += 1
            continue
        symbol = str(r.get("symbol") or "")
        if not symbol:
            bericht.verworfen["ohne_symbol"] += 1
            continue

        sid = str(r.get("schwinger_id") or "") or None
        gid = str(r.get("gegner_id") or "") or None
        if not sid and r.get("schwinger_name"):
            sid = index.finde(str(r["schwinger_name"]))
            if sid is None:
                unaufloesbar[str(r["schwinger_name"])] += 1
        if not gid and r.get("gegner_name"):
            gid = index.finde(str(r["gegner_name"]))
            if gid is None:
                unaufloesbar[str(r["gegner_name"])] += 1
        if not sid or not gid:
            bericht.verworfen["name_nicht_aufloesbar"] += 1
            continue
        if sid == gid:
            # Kann nur durch eine Fehlzuordnung entstehen -- niemand schwingt
            # gegen sich selbst. Früher landete so etwas still im Training.
            bericht.verworfen["schwinger_gegen_sich_selbst"] += 1
            continue
        if sid not in schwinger or gid not in schwinger:
            bericht.verworfen["id_nicht_im_kader"] += 1
            continue

        datum = str(r.get("datum") or "")[:10]
        roh.append(
            RohGangEintrag(
                event_id=event_id,
                datum=datum,
                schwinger_id=sid,
                gegner_id=gid,
                symbol=symbol,
                note=r.get("note"),
                fest_typ=str(r.get("fest_typ") or "regional"),
                kranz=bool(r.get("kranz", False)),
            )
        )

    bericht.n_roh_uebernommen = len(roh)
    bericht.n_namen_unaufloesbar = len(unaufloesbar)
    bericht.beispiele_unaufloesbar = [n for n, _ in unaufloesbar.most_common(10)]

    if not schwinger or not events or not roh:
        raise RuntimeError(
            "Für --source scrape fehlen brauchbare Rohdaten in artifacts/raw "
            f"(schwinger={len(schwinger)}, feste={len(events)}, gaenge={len(roh)}). "
            "Zuerst `python -m pipeline.fetch_raw` ausführen."
        )
    if mit_bericht:
        return schwinger, events, roh, bericht
    return schwinger, events, roh


def lade_kommende_feste(*, heute=None):
    """Kommende Feste + auf Schwinger-IDs gemappte Paarungen (FR-2).

    Rückgabe: ``(feste, diagnose)``. Die Diagnose landet im Qualitätsbericht,
    damit ein leerer Kalender als Befund erkennbar ist statt als Stille.
    """
    from .agenda import lade_kommende

    kommende, diagnose = lade_kommende(heute=heute)
    raw_s = _lade_raw_json("schwinger.json", {"schwinger": []}).get("schwinger", [])
    index = baue_namensindex(raw_s)
    for fest in kommende:
        gemappt = []
        for p in fest.get("paarungen_namen", []):
            a_id = index.finde(str(p.get("a_name", "")))
            b_id = index.finde(str(p.get("b_name", "")))
            if a_id and b_id and a_id != b_id:
                gemappt.append({"a_id": a_id, "b_id": b_id})
        if gemappt:
            fest["paarungen"] = gemappt
        fest.pop("paarungen_namen", None)
    diagnose["n_feste"] = len(kommende)
    diagnose["n_mit_paarungen"] = sum(1 for f in kommende if f.get("paarungen"))
    return kommende, diagnose
