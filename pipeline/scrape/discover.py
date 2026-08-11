"""Automatische Fest-Ermittlung über die schlussgang.ch JSON:API (Drupal).

    https://backend.schlussgang.ch/jsonapi/node/event

Listet alle Feste, die eine finale Statistik-PDF haben (field_final_statistic_pdf),
inkl. Metadaten (Name/Datum/Typ) und der aufgelösten PDF-URL. Damit muss keine
Fest-ID mehr hardcodiert werden — die Pipeline entdeckt neue Feste selbst (FR-6).
"""
from __future__ import annotations

import json
import urllib.request
from urllib.parse import urljoin

_HOST = "https://backend.schlussgang.ch"
_JSONAPI = f"{_HOST}/jsonapi/node/event"
_UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
       "Chrome/124.0.0.0 Safari/537.36")


def _get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={
        "User-Agent": _UA, "Accept": "application/vnd.api+json"})
    with urllib.request.urlopen(req, timeout=45) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def _pdf_url_aus_included(rel: dict | None, files: dict) -> str | None:
    if not rel:
        return None
    f = files.get(rel.get("id"))
    if not f:
        return None
    uri = f.get("attributes", {}).get("uri", {}) or {}
    pfad = uri.get("url")
    if not pfad and uri.get("value"):
        pfad = uri["value"].replace("public://", "/sites/default/files/")
    return urljoin(_HOST, pfad) if pfad else None


def liste_feste(max_feste: int = 60, max_seiten: int = 25) -> list[dict]:
    """Feste mit Statistik-PDF, jüngste zuerst.

    Rückgabe je Fest: {esv_id, name, datum, typ, pdf_url}.
    """
    url = (f"{_JSONAPI}?include=field_final_statistic_pdf"
           "&sort=-field_event_date&page[limit]=50")
    feste: list[dict] = []
    seiten = 0
    while url and len(feste) < max_feste and seiten < max_seiten:
        doc = _get_json(url)
        seiten += 1
        files = {inc["id"]: inc for inc in doc.get("included", [])
                 if str(inc.get("type", "")).startswith("file")}
        for e in doc.get("data", []):
            attrs = e.get("attributes", {})
            rel = (e.get("relationships", {})
                     .get("field_final_statistic_pdf", {}).get("data"))
            pdf_url = _pdf_url_aus_included(rel, files)
            if not pdf_url:
                continue
            feste.append({
                "esv_id": attrs.get("field_event_esv_id"),
                "name": attrs.get("field_event_esv_title") or attrs.get("title") or "",
                "datum": attrs.get("field_event_date"),
                "typ": attrs.get("field_event_type"),
                "pdf_url": pdf_url,
            })
        url = (doc.get("links", {}) or {}).get("next", {})
        url = url.get("href") if isinstance(url, dict) else None
    return feste[:max_feste]
