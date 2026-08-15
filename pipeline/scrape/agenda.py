"""Kommende Feste (FR-2, §4.1).

Primärquelle ist dieselbe JSON:API, aus der auch die abgeschlossenen Feste
kommen (``backend-api.schlussgang.ch/jsonapi/node/event``) -- nur ohne den
``finished``-Filter und ab heute statt rückwärts. Das ist aus zwei Gründen
robuster als die HTML-Agenda:

* Die API liefert die **Kategorie-Taxonomie** (``field_category``) mit, also
  denselben verlässlichen Fest-Typ wie bei den vergangenen Festen. Die
  Namensheuristik (``typ_von_name``) ist nur noch Notnagel.
* Sie hängt nicht am Markup einer serverseitig gerenderten Seite. Der frühere
  Weg über JSON-LD-``Event``-Blöcke auf ``schlussgang.ch/agenda`` lieferte
  dauerhaft 0 Treffer -- die Seite weist keine JSON-LD-Events (mehr) aus.

Der HTML/JSON-LD-Pfad bleibt als Fallback erhalten (``scrape_agenda``).
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta
from urllib.parse import urlencode

from .http import hole

AGENDA_URL = "https://www.schlussgang.ch/agenda"
EVENT_LIST_URL = "https://backend-api.schlussgang.ch/jsonapi/node/event"

# Wie weit in die Zukunft "kommend" reicht. Deckt die laufende Saison-Vorschau
# ab, ohne den kompletten Folgejahres-Kalender mitzuziehen.
HORIZONT_TAGE = 60

# Taxonomie "event_tags" (field_category) -> config.FEST_TYPEN. Eine Quelle der
# Wahrheit für vergangene UND kommende Feste (schlussgang_resultate importiert
# von hier). Jungschwingen/Frauenschwingen/Nationalturnen haben keine eigene
# Skalenstufe und fallen mangels Alternative auf "regional".
KATEGORIE_TYP = {
    "Eidgenössische Anlässe": "eidgenoessisch",
    "Bergkranzfest": "berg",
    "Teilverbandsfest": "teilverband",
    "Kantonal-/Gaufest": "kantonal",
    "Regionalfeste": "regional",
    "Jungschwingen": "regional",
    "Frauenschwingen": "regional",
    "Nationalturnen": "regional",
}

# Namensheuristik als Fallback. Wortgrenzen sind zwingend: ohne sie matchte
# "berg" mitten in Ortsnamen und stufte z.B. das "Bern-Jurassische Schwingfest
# Werdtberg" als Bergkranzfest ein.
_EVENT_TYP_RE = {
    "eidgenoessisch": re.compile(r"\beidg", re.IGNORECASE),
    # \bberg trifft "Bergkranzfest"/"Bergschwinget" (Wortanfang), aber NICHT
    # "Werdtberg"/"Sörenberg", wo "berg" nur Ortsnamen-Endung ist.
    "berg": re.compile(r"\bberg", re.IGNORECASE),
    "kantonal": re.compile(r"\bkantonal", re.IGNORECASE),
    "teilverband": re.compile(r"\bteilverband", re.IGNORECASE),
}

# Nur explizite Trenner ("vs", "gegen"). Ein blosser Bindestrich als Trenner
# erzeugte Phantom-Paarungen aus jedem Doppelnamen ("Bern-Jurassisch").
_PAIR_RE = re.compile(
    r"([A-ZÄÖÜ][A-Za-zÀ-ÖØ-öø-ÿ'`’\-. ]{1,60}?)\s*(?:vs\.?|gegen)\s+"
    r"([A-ZÄÖÜ][A-Za-zÀ-ÖØ-öø-ÿ'`’\-. ]{1,60})"
)


class AgendaLeer(RuntimeError):
    """Quelle war erreichbar, wies aber keine kommenden Feste aus."""


def _norm_space(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def typ_von_name(name: str) -> str:
    """Fest-Typ-Heuristik anhand des Namens (Fallback ohne Kategorie-Taxonomie)."""
    for t, rx in _EVENT_TYP_RE.items():
        if rx.search(name):
            return t
    return "regional"


def _datum_iso(raw: str) -> str | None:
    if not raw:
        return None
    raw = raw.strip()
    for k in (raw, raw[:10], raw.replace("Z", "+00:00")):
        try:
            if "T" in k:
                return datetime.fromisoformat(k).date().isoformat()
            return date.fromisoformat(k[:10]).isoformat()
        except ValueError:
            continue
    return None


def _extract_paarungen(text: str) -> list[tuple[str, str]]:
    paare: list[tuple[str, str]] = []
    for a, b in _PAIR_RE.findall(text):
        a_n, b_n = _norm_space(a), _norm_space(b)
        if a_n and b_n and a_n.lower() != b_n.lower():
            paare.append((a_n, b_n))
    seen, dedup = set(), []
    for a, b in paare:
        k = (a.lower(), b.lower())
        if k not in seen:
            seen.add(k)
            dedup.append((a, b))
    return dedup


# --- Primärquelle: JSON:API ---------------------------------------------

def kommende_url(offset: int, limit: int, *, ab_datum: str, bis_datum: str, typ: str) -> str:
    params = {
        "filter[ab][condition][path]": "field_event_date",
        "filter[ab][condition][value]": ab_datum,
        "filter[ab][condition][operator]": ">=",
        "filter[bis][condition][path]": "field_event_date",
        "filter[bis][condition][value]": bis_datum,
        "filter[bis][condition][operator]": "<=",
        "sort": "field_event_date",
        "page[limit]": limit,
        "page[offset]": offset,
        "include": "field_category",
        "fields[node--event]": (
            "drupal_internal__nid,title,field_title_custom,field_event_date,"
            "field_event_location,field_event_state,field_category"
        ),
        "fields[taxonomy_term--event_tags]": "name",
    }
    if typ:
        params["filter[typ][condition][path]"] = "field_event_type"
        params["filter[typ][condition][value]"] = typ
    return f"{EVENT_LIST_URL}?{urlencode(params)}"


def _kategorie_name(item: dict, included_by_id: dict[str, dict]) -> str | None:
    ref = ((item.get("relationships") or {}).get("field_category") or {}).get("data")
    if not isinstance(ref, dict):
        return None
    inc = included_by_id.get(ref.get("id"))
    return inc.get("attributes", {}).get("name") if inc else None


def parse_jsonapi_kommende(response: dict, *, heute: date) -> list[dict]:
    """Wandelt eine JSON:API-Antwort in kommende Feste um."""
    included_by_id = {inc["id"]: inc for inc in response.get("included") or []}
    events: list[dict] = []
    for item in response.get("data") or []:
        attrs = item.get("attributes") or {}
        nid = attrs.get("drupal_internal__nid")
        name = _norm_space(str(attrs.get("field_title_custom") or attrs.get("title") or ""))
        datum = _datum_iso(str(attrs.get("field_event_date") or ""))
        if not nid or not name or not datum or datum < heute.isoformat():
            continue
        # Ein Fest am heutigen Tag kann bereits abgeschlossen sein.
        if str(attrs.get("field_event_state") or "").lower() == "finished":
            continue
        kategorie = _kategorie_name(item, included_by_id)
        events.append(
            {
                "id": f"schlussgang-{nid}",
                "name": name,
                "datum": datum,
                "typ": KATEGORIE_TYP.get(kategorie or "") or typ_von_name(name),
                "kategorie": kategorie,
                "ort": attrs.get("field_event_location") or None,
                "quelle": "schlussgang.ch/event",
                "paarungen_namen": [],
            }
        )
    events.sort(key=lambda e: (e["datum"], e["name"]))
    return events


def scrape_kommende_feste(
    *,
    heute: date | None = None,
    horizont_tage: int = HORIZONT_TAGE,
    typ: str = "Aktivschwinger",
    page_size: int = 50,
) -> list[dict]:
    """Kommende Feste über die JSON:API (Primärpfad)."""
    heute = heute or date.today()
    bis = (heute + timedelta(days=horizont_tage)).isoformat()
    url = kommende_url(0, page_size, ab_datum=heute.isoformat(), bis_datum=bis, typ=typ)
    return parse_jsonapi_kommende(json.loads(hole(url)), heute=heute)


# --- Fallback: HTML/JSON-LD der Agenda-Seite -----------------------------

def _to_liste(obj) -> list[dict]:
    if isinstance(obj, list):
        return [x for x in obj if isinstance(x, dict)]
    if isinstance(obj, dict):
        if isinstance(obj.get("@graph"), list):
            return [x for x in obj["@graph"] if isinstance(x, dict)]
        return [obj]
    return []


def _extract_jsonld(html: str) -> list[dict]:
    out: list[dict] = []
    for raw in re.findall(
        r"<script[^>]*type=['\"]application/ld\+json['\"][^>]*>(.*?)</script>",
        html,
        flags=re.IGNORECASE | re.DOTALL,
    ):
        raw = raw.strip()
        if not raw:
            continue
        try:
            out.extend(_to_liste(json.loads(raw)))
        except json.JSONDecodeError:
            continue
    return out


def parse_agenda_html(html: str, *, heute: date | None = None) -> list[dict]:
    """Parst kommende Feste aus Agenda-HTML (JSON-LD-``Event``-Blöcke)."""
    heute = heute or date.today()
    events: list[dict] = []
    for item in _extract_jsonld(html):
        typ = item.get("@type")
        is_event = "Event" in typ if isinstance(typ, list) else typ == "Event"
        if not is_event:
            continue
        name = _norm_space(str(item.get("name") or ""))
        if not name:
            continue
        datum = _datum_iso(str(item.get("startDate") or ""))
        if not datum or datum < heute.isoformat():
            continue
        loc = item.get("location")
        ort = _norm_space(str(loc.get("name") or "")) or None if isinstance(loc, dict) else None
        paare = _extract_paarungen(_norm_space(str(item.get("description") or "")))
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        events.append(
            {
                "id": f"agenda-{datum}-{slug[:40]}",
                "name": name,
                "datum": datum,
                "typ": typ_von_name(name),
                "ort": ort,
                "quelle": "schlussgang.ch/agenda",
                "paarungen_namen": [{"a_name": a, "b_name": b} for a, b in paare],
            }
        )
    return events


def scrape_agenda() -> list[dict]:
    """Kommende Feste aus der HTML-Agenda (Fallback)."""
    return parse_agenda_html(hole(AGENDA_URL))


# --- Orchestrierung ------------------------------------------------------

def lade_kommende(*, heute: date | None = None) -> tuple[list[dict], dict]:
    """Kommende Feste laden: JSON:API zuerst, HTML-Agenda als Fallback.

    Rückgabe: ``(feste, diagnose)``. ``diagnose`` hält fest, welcher Pfad
    gegriffen hat und woran der jeweils andere scheiterte -- damit ein
    Fehlschlag im Qualitätsbericht sichtbar wird statt still zu bleiben.
    """
    heute = heute or date.today()
    diagnose: dict = {"pfad": None, "versuche": []}

    for pfad, fn in (("jsonapi", lambda: scrape_kommende_feste(heute=heute)),
                     ("agenda_html", lambda: parse_agenda_html(hole(AGENDA_URL), heute=heute))):
        try:
            feste = fn()
        except Exception as e:  # noqa: BLE001 - jeder Pfad darf scheitern
            diagnose["versuche"].append({"pfad": pfad, "fehler": f"{type(e).__name__}: {e}"})
            continue
        if feste:
            diagnose["pfad"] = pfad
            diagnose["versuche"].append({"pfad": pfad, "n": len(feste)})
            return feste, diagnose
        diagnose["versuche"].append({"pfad": pfad, "n": 0, "fehler": "keine kommenden Feste im Markup"})

    return [], diagnose
