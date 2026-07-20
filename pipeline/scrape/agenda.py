"""Agenda-Scraper: kommende Feste + (optionale) Paarungen (FR-2, §4.1)."""
from __future__ import annotations

import json
import re
from datetime import date, datetime

from .http import hole

AGENDA_URL = "https://www.schlussgang.ch/agenda"

_EVENT_TYP_RE = {
    "eidgenoessisch": re.compile(r"eidg", re.IGNORECASE),
    "berg": re.compile(r"berg", re.IGNORECASE),
    "kantonal": re.compile(r"kantonal", re.IGNORECASE),
    "teilverband": re.compile(r"teilverband", re.IGNORECASE),
}
_PAIR_RE = re.compile(
    r"([A-ZÄÖÜ][A-Za-zÀ-ÖØ-öø-ÿ'`’\-. ]{1,60})\s*(?:vs\.?|gegen|-)\s*"
    r"([A-ZÄÖÜ][A-Za-zÀ-ÖØ-öø-ÿ'`’\-. ]{1,60})"
)


def _norm_space(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def _typ_von_name(name: str) -> str:
    for t, rx in _EVENT_TYP_RE.items():
        if rx.search(name):
            return t
    return "regional"


def _datum_iso(raw: str) -> str | None:
    if not raw:
        return None
    raw = raw.strip()
    kandidaten = [
        raw,
        raw[:10],
        raw.replace("Z", "+00:00"),
    ]
    for k in kandidaten:
        try:
            if "T" in k:
                return datetime.fromisoformat(k).date().isoformat()
            return date.fromisoformat(k[:10]).isoformat()
        except ValueError:
            continue
    return None


def _to_liste(obj) -> list[dict]:
    if isinstance(obj, list):
        return [x for x in obj if isinstance(x, dict)]
    if isinstance(obj, dict):
        if "@graph" in obj and isinstance(obj["@graph"], list):
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


def _extract_paarungen(text: str) -> list[tuple[str, str]]:
    paare: list[tuple[str, str]] = []
    for a, b in _PAIR_RE.findall(text):
        a_n = _norm_space(a)
        b_n = _norm_space(b)
        if a_n and b_n and a_n != b_n:
            paare.append((a_n, b_n))
    # deterministisch deduplizieren
    seen = set()
    dedup = []
    for a, b in paare:
        k = (a.lower(), b.lower())
        if k in seen:
            continue
        seen.add(k)
        dedup.append((a, b))
    return dedup


def parse_agenda_html(html: str, *, heute: date | None = None) -> list[dict]:
    """Parst kommende Feste aus Agenda-HTML (bevorzugt JSON-LD)."""
    heute = heute or date.today()
    events: list[dict] = []
    for item in _extract_jsonld(html):
        typ = item.get("@type")
        if isinstance(typ, list):
            is_event = "Event" in typ
        else:
            is_event = typ == "Event"
        if not is_event:
            continue
        name = _norm_space(str(item.get("name") or ""))
        if not name:
            continue
        datum = _datum_iso(str(item.get("startDate") or ""))
        if not datum or datum < heute.isoformat():
            continue
        ort = None
        loc = item.get("location")
        if isinstance(loc, dict):
            ort = _norm_space(str(loc.get("name") or "")) or None
        desc = _norm_space(str(item.get("description") or ""))
        paare = _extract_paarungen(desc)
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        events.append(
            {
                "id": f"agenda-{datum}-{slug[:40]}",
                "name": name,
                "datum": datum,
                "typ": _typ_von_name(name),
                "ort": ort,
                "quelle": "schlussgang.ch/agenda",
                "paarungen_namen": [{"a_name": a, "b_name": b} for a, b in paare],
            }
        )
    return events


def scrape_agenda() -> list[dict]:
    """Kommende Feste inkl. optionaler Paarungen (namenbasiert)."""
    html = hole(AGENDA_URL)
    return parse_agenda_html(html)
