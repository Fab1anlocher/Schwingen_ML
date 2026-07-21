"""Schlussgang-Porträts scrapen und als Schwinger-Rohdaten normalisieren."""
from __future__ import annotations

import json
import re
from urllib.parse import urlencode, urljoin

from ..schema import schwinger_key
from .http import hole

BASE_URL = "https://www.schlussgang.ch"
LIST_API_URL = "https://backend-api.schlussgang.ch/jsonapi/node/portrait"


def _listen_url(offset: int, limit: int) -> str:
    params = {
        "filter[status]": 1,
        "filter[field_portrait_activity.tid]": 23,
        "filter[field_portrait_status.tid][value]": 20,
        "filter[field_portrait_status.tid][operator]": "NOT IN",
        "include": (
            "field_portrait_image,field_portrait_activity,field_portrait_association,"
            "field_portrait_status,field_portrait_club,field_portrait_cant_association"
        ),
        "page[limit]": limit,
        "page[offset]": offset,
        "sort": "field_portrait_last_name,field_portrait_first_name",
        "fields[node--portrait]": (
            "title,path,drupal_internal__nid,field_portrait_first_name,"
            "field_portrait_last_name,field_portrait_image,field_portrait_activity,"
            "field_portrait_association,field_portrait_status,field_portrait_search_strings,"
            "field_portrait_birthday,field_portrait_body_size,field_portrait_body_weight,"
            "field_portrait_senneturner,field_portrait_favorite_moves,"
            "field_portrait_wreath_status,field_portrait_schwingerkoenig,"
            "field_portrait_club,field_portrait_cant_association"
        ),
        "fields[file--file]": "uri,resourceIdObjMeta",
        "fields[taxonomy_term--portrait_activity]": "name,tid",
        "fields[taxonomy_term--portrait_status]": "name,tid",
        "fields[taxonomy_term--association]": "name,tid",
        "fields[taxonomy_term--club]": "name,tid",
        "fields[taxonomy_term--canton_association]": "name,tid",
        "jsonapi_include": 1,
    }
    return f"{LIST_API_URL}?{urlencode(params)}"


def _format_name(item: dict) -> str:
    first = str(item.get("field_portrait_first_name") or "").strip()
    last = str(item.get("field_portrait_last_name") or "").strip()
    title = str(item.get("title") or "").strip()
    if first and last:
        return f"{first} {last}".strip()
    if title:
        return title.split(",")[0].strip()
    return ""


def _kranzstatus(
    wreath_status: str, ist_koenig: bool, status_name: str, counts: dict[str, int]
) -> str:
    """Kranzstatus primär aus field_portrait_wreath_status ('*'/'**'/'***', s.
    auch das Sterne-Schema in den Statistik-PDFs) + schwingerkoenig-Flag.
    Fallback auf die Text-Heuristik für ältere Profile ohne diese Felder.
    """
    if ist_koenig:
        return "koenig"
    if wreath_status == "***":
        return "eidgenosse"
    if wreath_status in ("*", "**"):
        return "kranzer"
    s = status_name.lower()
    if counts.get("ESAF", 0) > 0 or "eidgen" in s:
        return "eidgenosse"
    if counts.get("Kränze", 0) > 0 or "kranz" in s:
        return "kranzer"
    return "kein"


def _geburtsjahr_aus_title(title: str) -> int | None:
    m = re.search(r"\b(19\d{2}|20\d{2})-\d{2}-\d{2}\b", title)
    return int(m.group(0)[:4]) if m else None


def _zu_float(wert) -> float | None:
    try:
        return float(str(wert).strip().replace(",", "."))
    except (TypeError, ValueError):
        return None


_SENNE_TURNER = {"S": "senne", "T": "turner"}


def scrape_schlussgang_portraets(max_profiles: int | None = None, page_size: int = 100) -> list[dict]:
    """Lädt Porträts von Schlussgang und normalisiert sie ins Rohschema."""
    raw_profiles: list[dict] = []
    offset = 0
    while True:
        response = json.loads(hole(_listen_url(offset, page_size)))
        items = response.get("data", [])
        if not items:
            break
        for item in items:
            if max_profiles is not None and len(raw_profiles) >= max_profiles:
                return raw_profiles
            alias = str(item.get("path", {}).get("alias") or "").strip()
            if not alias:
                continue
            profile_url = urljoin(BASE_URL, alias)

            name = _format_name(item)
            if not name:
                continue
            title = str(item.get("title") or "").strip()
            geburtstag = str(item.get("field_portrait_birthday") or "")
            jahrgang = (
                int(geburtstag[:4])
                if len(geburtstag) >= 4 and geburtstag[:4].isdigit()
                else _geburtsjahr_aus_title(title)
            )
            status_name = str((item.get("field_portrait_status") or {}).get("name") or "")
            association = str((item.get("field_portrait_association") or {}).get("name") or "")
            kanton = str((item.get("field_portrait_cant_association") or {}).get("name") or "")
            schwingklub = str((item.get("field_portrait_club") or {}).get("name") or "")
            image_url = str((item.get("field_portrait_image") or {}).get("uri", {}).get("url") or "")
            counts = _status_counts(status_name)
            wreath_status = str(item.get("field_portrait_wreath_status") or "")
            ist_koenig = bool(item.get("field_portrait_schwingerkoenig"))
            schwuenge = [
                s.strip()
                for s in str(item.get("field_portrait_favorite_moves") or "").split(",")
                if s.strip()
            ]

            portrait = {
                "id": schwinger_key(name, jahrgang),
                "name": name,
                "jahrgang": jahrgang,
                "groesse_cm": _zu_float(item.get("field_portrait_body_size")),
                "gewicht_kg": _zu_float(item.get("field_portrait_body_weight")),
                "kranzstatus": _kranzstatus(wreath_status, ist_koenig, status_name, counts),
                "teilverband": association or None,
                "kanton": kanton or None,
                "schwingklub": schwingklub or None,
                "senne_turner": _SENNE_TURNER.get(str(item.get("field_portrait_senneturner") or "")),
                "bevorzugte_schwuenge": schwuenge,
                "quellen": [
                    "schlussgang.ch/portraet",
                    profile_url,
                ],
                "portrait_status": status_name or None,
                "portrait_counts": counts,
                "portrait_image": image_url or None,
                "portrait_search_strings": item.get("field_portrait_search_strings"),
                "portrait_title": title or None,
                "portrait_uuid": item.get("id"),
            }
            raw_profiles.append(portrait)
        if len(items) < page_size:
            break
        offset += page_size
    return raw_profiles


def _status_counts(status_name: str) -> dict[str, int]:
    s = status_name.lower()
    if "eidgen" in s:
        return {"Kränze": 0, "ESAF": 1, "Berg": 0, "Teilverband": 0, "Kantonal/Gau": 0, "Kranzfestsiege": 0}
    if "kranz" in s:
        return {"Kränze": 1, "ESAF": 0, "Berg": 0, "Teilverband": 0, "Kantonal/Gau": 0, "Kranzfestsiege": 0}
    return {"Kränze": 0, "ESAF": 0, "Berg": 0, "Teilverband": 0, "Kantonal/Gau": 0, "Kranzfestsiege": 0}


def write_schwinger_json(path, profiles: list[dict]) -> None:
    payload = {"schwinger": [{k: v for k, v in profile.items() if not k.startswith("portrait_")} for profile in profiles]}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_schlussgang_raw_json(path, profiles: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"profiles": profiles}, ensure_ascii=False, indent=2), encoding="utf-8")