"""ESV-Statistikseite scrapen und die PDF-Downloads als Rohdaten erfassen."""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode

from bs4 import BeautifulSoup

from .http import hole

STATS_URL = "https://esv.ch/ranglisten/statistiken/"


def _pdf_text(pdf_bytes: bytes) -> str:
    import io

    try:
        import pdfplumber  # type: ignore
    except ImportError as exc:  # noqa: BLE001
        raise RuntimeError(
            "pdfplumber ist nicht installiert; bitte requirements-pipeline.txt aktivieren."
        ) from exc

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


def _download_url(jahr: int, button_name: str, button_value: str) -> str:
    params = urlencode({"jahr": jahr, button_name: button_value})
    return f"https://esv.ch/kranzzahlen/?{params}"


def scrape_esv_statistiken(jahr: int = 2026, *, download_pdfs: bool = False) -> dict:
    """Lädt die ESV-Statistikseite und optional die PDF-Downloads der Kranzzahlen."""
    html = hole(STATS_URL)
    soup = BeautifulSoup(html, "html.parser")

    downloads: list[dict] = []
    for form in soup.find_all("form"):
        action = str(form.get("action") or "")
        if "/kranzzahlen/" not in action:
            continue
        buttons = form.find_all("button", attrs={"type": "submit"})
        for button in buttons:
            button_name = str(button.get("name") or "").strip()
            button_value = str(button.get("value") or "").strip()
            if not button_name or not button_value:
                continue
            label = button.get_text(" ", strip=True)
            download_url = _download_url(jahr, button_name, button_value)
            eintrag = {
                "jahr": jahr,
                "label": label,
                "download_url": download_url,
                "content_type": "application/pdf",
            }
            if download_pdfs:
                pdf_bytes = hole(download_url, binaer=True)
                eintrag["pdf_bytes"] = len(pdf_bytes)
                eintrag["text"] = _pdf_text(pdf_bytes)
            downloads.append(eintrag)

    direct_links = []
    for link in soup.find_all("a", href=True):
        href = str(link.get("href") or "")
        if href.lower().endswith(".pdf"):
            direct_links.append(
                {
                    "label": link.get_text(" ", strip=True),
                    "url": href,
                }
            )

    return {
        "quelle": STATS_URL,
        "gescrapt_am": datetime.utcnow().isoformat() + "Z",
        "jahr": jahr,
        "downloads": downloads,
        "direkte_pdfs": direct_links,
    }


def write_esv_stats_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")