"""Echte Datenquellen-Scraper (§4.1)."""
from __future__ import annotations

import json
from pathlib import Path

from ..labels import RohGangEintrag
from ..schema import Event, Schwinger, normalize_name, schwinger_key

RAW_DIR = Path(__file__).resolve().parent.parent.parent / "artifacts" / "raw"


def _lade_raw_json(name: str, default):
    p = RAW_DIR / name
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))


def schwinger_index(schwinger: dict[str, Schwinger]) -> dict[str, str]:
    idx: dict[str, str] = {}
    for sid, s in schwinger.items():
        idx[normalize_name(s.name)] = sid
    return idx


def map_name(name: str, idx: dict[str, str]) -> str | None:
    n = normalize_name(name)
    if n in idx:
        return idx[n]
    teile = n.split()
    if len(teile) >= 2:
        kandidaten = [sid for nm, sid in idx.items() if all(t in nm for t in teile)]
        if len(kandidaten) == 1:
            return kandidaten[0]
    return None


def lade_echte_daten():
    """Lädt echte Daten aus lokalen Raw-Dateien (artifacts/raw).

    Erwartete Dateien:
      - schwinger.json: {"schwinger":[...]}
      - events.json: {"events":[...]}
      - gaenge.json: {"gaenge":[...]} (Roh-Perspektiven mit Symbolen)
    """
    raw_s = _lade_raw_json("schwinger.json", {"schwinger": []}).get("schwinger", [])
    raw_e = _lade_raw_json("events.json", {"events": []}).get("events", [])
    raw_g = _lade_raw_json("gaenge.json", {"gaenge": []}).get("gaenge", [])

    schwinger: dict[str, Schwinger] = {}
    for r in raw_s:
        name = str(r.get("name", "")).strip()
        if not name:
            continue
        jg = r.get("jahrgang")
        sid = r.get("id") or schwinger_key(name, jg)
        sw = r.get("bevorzugte_schwuenge") or r.get("schwuenge") or []
        schwinger[sid] = Schwinger(
            id=sid,
            name=name,
            jahrgang=jg,
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

    events: list[Event] = []
    for r in raw_e:
        if not r.get("id") or not r.get("datum") or not r.get("name"):
            continue
        events.append(
            Event(
                id=str(r["id"]),
                name=str(r["name"]),
                datum=str(r["datum"])[:10],
                typ=str(r.get("typ") or "regional"),
                ort=r.get("ort"),
                quelle=str(r.get("quelle") or "schlussgang.ch"),
            )
        )

    roh: list[RohGangEintrag] = []
    idx = schwinger_index(schwinger)
    for r in raw_g:
        event_id = str(r.get("event_id") or "")
        datum = str(r.get("datum") or "")[:10]
        fest_typ = str(r.get("fest_typ") or "regional")
        symbol = str(r.get("symbol") or "")
        sid = r.get("schwinger_id")
        gid = r.get("gegner_id")
        if not sid and r.get("schwinger_name"):
            sid = map_name(str(r.get("schwinger_name")), idx)
        if not gid and r.get("gegner_name"):
            gid = map_name(str(r.get("gegner_name")), idx)
        if not (event_id and datum and sid and gid and symbol):
            continue
        roh.append(
            RohGangEintrag(
                event_id=event_id,
                datum=datum,
                schwinger_id=str(sid),
                gegner_id=str(gid),
                symbol=symbol,
                note=r.get("note"),
                fest_typ=fest_typ,
            )
        )

    if not schwinger or not events or not roh:
        raise RuntimeError(
            "Für --source scrape fehlen lokale Raw-Daten in artifacts/raw "
            "(schwinger.json, events.json, gaenge.json)."
        )
    return schwinger, events, roh


def lade_kommende_feste():
    """Kommende Feste + gemappte Paarungen (FR-2)."""
    from .agenda import scrape_agenda

    kommende = scrape_agenda()
    try:
        raw_s = _lade_raw_json("schwinger.json", {"schwinger": []}).get("schwinger", [])
        idx = {normalize_name(str(s.get("name", ""))): str(s.get("id")) for s in raw_s if s.get("id")}
        for fest in kommende:
            mapped = []
            for p in fest.get("paarungen_namen", []):
                a_id = map_name(str(p.get("a_name", "")), idx)
                b_id = map_name(str(p.get("b_name", "")), idx)
                if a_id and b_id and a_id != b_id:
                    mapped.append({"a_id": a_id, "b_id": b_id})
            if mapped:
                fest["paarungen"] = mapped
            fest.pop("paarungen_namen", None)
    except Exception:
        for fest in kommende:
            fest.pop("paarungen_namen", None)
    return kommende
