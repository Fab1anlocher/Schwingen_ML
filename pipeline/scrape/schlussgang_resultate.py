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

from .agenda import KATEGORIE_TYP as _KATEGORIE_TYP, typ_von_name
from .http import hole
from .schlussgang_pdf import parse_pdf_bytes, pdf_url

from . import EVENT_ID_PRAEFIX  # noqa: E402  (eine Quelle der Wahrheit)

EVENT_LIST_URL = "https://backend-api.schlussgang.ch/jsonapi/node/event"



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
        "include": "field_category,field_final_ranking_pdf",
        "fields[node--event]": (
            "drupal_internal__nid,title,field_title_custom,field_event_date,"
            "field_event_location,field_event_esv_id,field_category,field_final_ranking_pdf"
        ),
        "fields[taxonomy_term--event_tags]": "name",
        "fields[file--file]": "uri",
    }
    if typ:
        params["filter[typ][condition][path]"] = "field_event_type"
        params["filter[typ][condition][value]"] = typ
    return f"{EVENT_LIST_URL}?{urlencode(params)}"


def _rangliste_url(item: dict, included_by_id: dict[str, dict]) -> str | None:
    """Absolute URL der Schlussrangliste (field_final_ranking_pdf) oder None.

    Meist <nid>-final.pdf, aber nicht immer (ESAF 2025 liegt unter
    2025-09/Schlussrangliste.pdf) -- darum aus der API statt aus einem Muster.
    """
    ref = ((item.get("relationships") or {}).get("field_final_ranking_pdf") or {}).get("data")
    if not isinstance(ref, dict):
        return None
    uri = ((included_by_id.get(ref.get("id")) or {}).get("attributes") or {}).get("uri") or {}
    pfad = uri.get("url") if isinstance(uri, dict) else None
    return f"https://www.schlussgang.ch{pfad}" if pfad else None


def _kategorie_name(item: dict, included_by_id: dict[str, dict]) -> str | None:
    rel = (item.get("relationships") or {}).get("field_category") or {}
    ref = rel.get("data")
    if not isinstance(ref, dict):
        return None
    inc = included_by_id.get(ref.get("id"))
    if not inc:
        return None
    return inc.get("attributes", {}).get("name")


# Sicherheitsgrenze für die Blätterschleife. Ignoriert die API ein `page[offset]`
# (oder ändert sie ihr Verhalten), liefe die Schleife sonst endlos und lüde
# dieselben Feste immer wieder -- bei 2 s Rate-Limit je PDF sind das schnell
# Stunden. Bewusst grosszügig: die echte Historie liegt weit darunter.
MAX_SEITEN = 60


def scrape_events(
    max_events: int | None = None,
    *,
    seit_datum: str = "2024-01-01",
    typ: str = "Aktivschwinger",
    page_size: int = 50,
) -> list[dict]:
    """Lädt abgeschlossene Feste (Standard: Aktivschwinger).

    Bricht ab, sobald eine Seite kein einziges neues Fest mehr liefert --
    dann blättert die API nicht weiter, und Weitermachen würde nur Duplikate
    erzeugen.
    """
    events: list[dict] = []
    gesehen: set[str] = set()
    offset = 0
    for seite in range(MAX_SEITEN):
        response = json.loads(hole(_listen_url(offset, page_size, seit_datum=seit_datum, typ=typ)))
        items = response.get("data", [])
        if not items:
            break
        included_by_id = {inc["id"]: inc for inc in response.get("included", [])}
        neu_auf_seite = 0
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
            if f"schlussgang-{nid}" in gesehen:
                continue  # dieselbe Seite nochmals erhalten
            gesehen.add(f"schlussgang-{nid}")
            neu_auf_seite += 1
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
                    "rangliste_url": _rangliste_url(item, included_by_id),
                }
            )
        if neu_auf_seite == 0:
            print(f"      (Blättern beendet: Seite {seite + 1} brachte keine neuen Feste)", flush=True)
            break
        if len(items) < page_size:
            break
        offset += page_size
    else:
        print(f"      (Seitenlimit {MAX_SEITEN} erreicht -- Historie evtl. unvollständig)", flush=True)
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


def vervollstaendige_rangliste_urls(
    events: list[dict], schon_geladen: set[str], *, typ: str = "Aktivschwinger"
) -> int:
    """Trägt fehlende ``rangliste_url`` nach (ältere Cache-Einträge kennen sie nicht).

    Nur für Feste, deren Rangliste noch nicht im Cache liegt. Eine reine
    Listenabfrage (kein PDF), also wenige Anfragen -- und nötig, weil drei
    Feste nicht dem Muster <nid>-final.pdf folgen, darunter das ESAF 2025.
    Gibt die Zahl ergänzter URLs zurück; ``events`` wird in-place ergänzt.
    """
    offen = [e for e in events if not e.get("rangliste_url") and str(e["id"]) not in schon_geladen]
    if not offen:
        return 0
    seit = min(str(e.get("datum") or "")[:10] for e in offen)
    urls = {e["id"]: e.get("rangliste_url") for e in scrape_events(None, seit_datum=seit, typ=typ)}
    n = 0
    for e in offen:
        if urls.get(e["id"]):
            e["rangliste_url"] = urls[e["id"]]
            n += 1
    return n


def rangliste_url_fallback(nid) -> str:
    """Übliches Muster, falls ein älterer Cache-Eintrag die URL noch nicht führt."""
    return f"https://www.schlussgang.ch/sites/default/files/event-ranking-list/{nid}-final.pdf"


def lade_rangliste(event: dict) -> list[dict]:
    """Schlussrangliste eines Fests laden + parsen, inkl. Kranz je Teilnehmer."""
    from .schlussgang_rangliste import mit_kranz, parse_rangliste

    url = event.get("rangliste_url") or rangliste_url_fallback(event["nid"])
    return mit_kranz(parse_rangliste(hole(url, binaer=True)))


def ergaenze_ranglisten(path: Path, events: list[dict], *, neu_laden: set[str] = frozenset()) -> dict:
    """artifacts/raw/ranglisten.json additiv um fehlende Feste ergänzen.

    Beim ersten Lauf ist das ein Nachladen der ganzen Historie (rund 480 PDFs,
    2 s Abstand -> ~16 min), danach nur neue Feste. Ein Fest, dessen Liste
    nicht lesbar war, wird mit ``fehler`` vermerkt und nicht täglich erneut
    versucht; ``neu_laden`` erzwingt es für bestimmte IDs (z.B. die frisch
    geladenen, falls ein Resultat nachgetragen wurde).
    """
    daten: dict = {}
    if path.exists():
        daten = json.loads(path.read_text(encoding="utf-8")).get("ranglisten", {})
    offen = [e for e in events if str(e["id"]) not in daten or str(e["id"]) in neu_laden]
    print(f"      Schlussranglisten: {len(daten)} im Cache, {len(offen)} zu laden", flush=True)
    for i, event in enumerate(offen, start=1):
        eid = str(event["id"])
        try:
            eintraege = lade_rangliste(event)
            daten[eid] = {"eintraege": eintraege}
            n_kranz = sum(1 for e in eintraege if e.get("kranz"))
            meldung = f"{len(eintraege)} Teilnehmer, {n_kranz} Kränze"
        except Exception as ex:  # noqa: BLE001 - ein Fest darf den Rest nicht blockieren
            daten[eid] = {"fehler": f"{type(ex).__name__}: {ex}"[:200]}
            meldung = f"nicht lesbar ({daten[eid]['fehler']})"
        if i % 25 == 0 or i == len(offen) or "fehler" in daten[eid]:
            print(f"      [{i}/{len(offen)}] {event.get('datum')} {event.get('name')}: {meldung}", flush=True)
        if i % 50 == 0:  # Zwischenstand sichern: ein Abbruch verliert nicht alles
            _schreibe_ranglisten(path, daten)
    _schreibe_ranglisten(path, daten)
    return daten


def _schreibe_ranglisten(path: Path, daten: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"ranglisten": daten}, ensure_ascii=False), encoding="utf-8")
