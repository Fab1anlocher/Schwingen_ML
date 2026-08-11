"""Vergangene Feste + Gänge von schlussgang.ch (§4.1, primäre Quelle).

Listet abgeschlossene Feste über die JSON:API (node/event, analog zu
schlussgang_portraet.py), lädt je Fest die finale Statistik-PDF und
parst sie über schlussgang_pdf.py zu Roh-Gang-Einträgen.

Der Kader (inkl. Teilnehmer ohne Porträt) wird NICHT hier ergänzt, sondern
zustandslos aus Porträts + PDF-Namen gebaut -- s. ``pipeline.roster``.
"""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlencode

from .agenda import typ_von_name
from .http import hole
from .schlussgang_pdf import parse_pdf_bytes, pdf_url

from . import EVENT_ID_PRAEFIX  # noqa: E402  (eine Quelle der Wahrheit)

EVENT_LIST_URL = "https://backend-api.schlussgang.ch/jsonapi/node/event"

# Taxonomie "event_tags" (field_category) -> config.FEST_TYPEN. Jungschwingen/
# Frauenschwingen/Nationalturnen haben keine eigene Skalenstufe und fallen
# mangels Alternative auf "regional".
_KATEGORIE_TYP = {
    "Eidgenössische Anlässe": "eidgenoessisch",
    "Bergkranzfest": "berg",
    "Teilverbandsfest": "teilverband",
    "Kantonal-/Gaufest": "kantonal",
    "Regionalfeste": "regional",
    "Jungschwingen": "regional",
    "Frauenschwingen": "regional",
    "Nationalturnen": "regional",
}


def _listen_url(offset: int, limit: int, *, seit_datum: str, typ: str) -> str:
    params = {
        "filter[state][condition][path]": "field_event_state",
        "filter[state][condition][value]": "finished",
        "filter[datum][condition][path]": "field_event_date",
        "filter[datum][condition][value]": seit_datum,
        "filter[datum][condition][operator]": ">=",
        "sort": "-field_event_date",
        "page[limit]": limit,
        "page[offset]": offset,
        "include": "field_category",
        "fields[node--event]": (
            "drupal_internal__nid,title,field_title_custom,field_event_date,"
            "field_event_location,field_event_esv_id,field_category"
        ),
        "fields[taxonomy_term--event_tags]": "name",
    }
    if typ:
        params["filter[typ][condition][path]"] = "field_event_type"
        params["filter[typ][condition][value]"] = typ
    return f"{EVENT_LIST_URL}?{urlencode(params)}"


def _kategorie_name(item: dict, included_by_id: dict[str, dict]) -> str | None:
    rel = (item.get("relationships") or {}).get("field_category") or {}
    ref = rel.get("data")
    if not isinstance(ref, dict):
        return None
    inc = included_by_id.get(ref.get("id"))
    if not inc:
        return None
    return inc.get("attributes", {}).get("name")


def scrape_events(
    max_events: int | None = None,
    *,
    seit_datum: str = "2024-01-01",
    typ: str = "Aktivschwinger",
    page_size: int = 50,
) -> list[dict]:
    """Lädt abgeschlossene Feste (Standard: Aktivschwinger, s. README §"MVP-Datensatz")."""
    events: list[dict] = []
    offset = 0
    while True:
        response = json.loads(hole(_listen_url(offset, page_size, seit_datum=seit_datum, typ=typ)))
        items = response.get("data", [])
        if not items:
            break
        included_by_id = {inc["id"]: inc for inc in response.get("included", [])}
        for item in items:
            if max_events is not None and len(events) >= max_events:
                return events
            attrs = item.get("attributes", {})
            nid = attrs.get("drupal_internal__nid")
            datum = attrs.get("field_event_date")
            name = attrs.get("field_title_custom") or attrs.get("title") or ""
            name = name.strip()
            if not nid or not datum or not name:
                continue
            kategorie = _kategorie_name(item, included_by_id)
            fest_typ = _KATEGORIE_TYP.get(kategorie or "") or typ_von_name(name)
            events.append(
                {
                    "id": f"schlussgang-{nid}",
                    "nid": nid,
                    "esv_id": attrs.get("field_event_esv_id"),
                    "name": name,
                    "datum": str(datum)[:10],
                    "typ": fest_typ,
                    "kategorie": kategorie,
                    "ort": attrs.get("field_event_location"),
                    "quelle": "schlussgang.ch/event",
                }
            )
        if len(items) < page_size:
            break
        offset += page_size
    return events


def lade_gaenge_fuer_event(event: dict) -> list[dict]:
    """Statistik-PDF eines Fests laden + zu Roh-Gang-Einträgen parsen."""
    pdf_bytes = hole(pdf_url(event["nid"]), binaer=True)
    return parse_pdf_bytes(
        pdf_bytes, event_id=event["id"], datum=event["datum"], fest_typ=event["typ"]
    )


def scrape_events_und_gaenge(
    max_events: int | None = None,
    *,
    seit_datum: str = "2024-01-01",
    typ: str = "Aktivschwinger",
) -> tuple[list[dict], list[dict]]:
    """Feste + Gänge in einem Rutsch (überspringt Feste ohne abrufbare PDF)."""
    print("      Feste-Liste laden ...", flush=True)
    events = scrape_events(max_events, seit_datum=seit_datum, typ=typ)
    print(f"      {len(events)} abgeschlossene Feste gefunden, lade Statistik-PDFs ...", flush=True)
    alle_gaenge: list[dict] = []
    geladene_events: list[dict] = []
    for i, event in enumerate(events, start=1):
        try:
            gaenge = lade_gaenge_fuer_event(event)
        except Exception as e:  # noqa: BLE001 - einzelnes Fest darf den Rest nicht blockieren
            print(f"      [{i}/{len(events)}] {event['name']}: PDF nicht ladbar/parsbar: {e}", flush=True)
            continue
        alle_gaenge.extend(gaenge)
        geladene_events.append(event)
        print(
            f"      [{i}/{len(events)}] {event['datum']} {event['name']}: "
            f"{len(gaenge)} Roh-Gang-Einträge",
            flush=True,
        )
    return geladene_events, alle_gaenge


def merge_events_raw_json(path: Path, neue_events: list[dict]) -> list[dict]:
    """events.json additiv aktualisieren (per Event-ID), statt zu überschreiben.

    Wichtig für den täglichen Cron-Lauf (NFR-1): ein enges `--seit-datum`-
    Fenster darf die zuvor gesammelte Historie nicht verwerfen.

    Zugleich werden Einträge ohne offizielle ``schlussgang-<nid>``-ID entfernt.
    Der Cache ist additiv und kannte bisher keinen Weg, etwas wieder
    loszuwerden -- so haben es Testfeste ("Testschwinget", ``ev-2026-test``)
    bis in die ausgelieferten Artefakte geschafft und dort sogar das jüngste
    Fest-Datum bestimmt.
    """
    vorhandene: list[dict] = []
    if path.exists():
        vorhandene = json.loads(path.read_text(encoding="utf-8")).get("events", [])
    nach_id = {str(e.get("id")): e for e in vorhandene}
    for e in neue_events:
        nach_id[str(e["id"])] = e
    zusammengefuehrt = sorted(
        (e for eid, e in nach_id.items() if eid.startswith(EVENT_ID_PRAEFIX)),
        key=lambda e: (e.get("datum") or "", e.get("id")),
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"events": zusammengefuehrt}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return zusammengefuehrt


def merge_gaenge_raw_json(
    path: Path, neue_gaenge: list[dict], event_ids: set[str], *, bekannte_events: set[str] | None = None
) -> list[dict]:
    """gaenge.json additiv aktualisieren.

    Gänge der frisch geladenen Feste werden ersetzt (ein Re-Parse desselben
    Fests darf nicht duplizieren), Gänge früher geladener Feste bleiben
    erhalten. ``bekannte_events`` (optional) entfernt verwaiste Gänge, deren
    Fest nicht mehr in events.json steht.
    """
    vorhandene: list[dict] = []
    if path.exists():
        vorhandene = json.loads(path.read_text(encoding="utf-8")).get("gaenge", [])
    behalten = [g for g in vorhandene if str(g.get("event_id")) not in event_ids]
    zusammengefuehrt = behalten + neue_gaenge
    if bekannte_events is not None:
        zusammengefuehrt = [
            g for g in zusammengefuehrt if str(g.get("event_id")) in bekannte_events
        ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"gaenge": zusammengefuehrt}, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return zusammengefuehrt
