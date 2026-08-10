"""Höflicher HTTP-Client (NFR-4): Rate-Limit, User-Agent, robots.txt.

Verwendet nur die Standardbibliothek, um die Abhängigkeiten der Pipeline
klein zu halten (GitHub-Actions-Runner, §7).
"""
from __future__ import annotations

import time
import urllib.request
import urllib.robotparser
from urllib.parse import urlparse

from ..config import SCRAPE_DELAY_SEKUNDEN, USER_AGENT

_letzter_request: dict[str, float] = {}
_robots_cache: dict[str, urllib.robotparser.RobotFileParser] = {}


def _robots(host: str) -> urllib.robotparser.RobotFileParser:
    if host not in _robots_cache:
        rp = urllib.robotparser.RobotFileParser()
        rp.set_url(f"https://{host}/robots.txt")
        try:
            rp.read()
        except Exception:  # noqa: BLE001 - robots nicht erreichbar -> konservativ
            pass
        _robots_cache[host] = rp
    return _robots_cache[host]


def darf_abrufen(url: str) -> bool:
    """robots.txt-Prüfung (NFR-4)."""
    host = urlparse(url).netloc
    return _robots(host).can_fetch(USER_AGENT, url)


def hole(url: str, *, binaer: bool = False):
    """GET mit Rate-Limit pro Host und robots.txt-Respekt."""
    host = urlparse(url).netloc
    if not darf_abrufen(url):
        raise PermissionError(f"robots.txt verbietet Abruf: {url}")
    # Rate-Limit pro Host.
    warte = SCRAPE_DELAY_SEKUNDEN - (time.time() - _letzter_request.get(host, 0))
    if warte > 0:
        time.sleep(warte)
    # Browser-ähnliche Header: viele Seiten (inkl. esv.ch) antworten sonst mit
    # 403 auf nicht-Browser-User-Agents. Rate-Limit + robots.txt bleiben aktiv.
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "de-CH,de;q=0.9,en;q=0.8",
        "Accept-Encoding": "identity",
        "Connection": "close",
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            daten = resp.read()
    except urllib.error.HTTPError as e:
        # esv.ch blockt Nicht-Browser-Clients/Cloud-IPs mit 403 (WAF). Auf einer
        # Wohn-IP kann ein echter Browser (Playwright) helfen: opt-in per
        # Umgebungsvariable SCHWINGEN_USE_BROWSER=1.
        if e.code == 403 and _browser_aktiv() and not binaer:
            _letzter_request[host] = time.time()
            return hole_via_browser(url)
        raise
    _letzter_request[host] = time.time()
    return daten if binaer else daten.decode("utf-8", errors="replace")


def _browser_aktiv() -> bool:
    import os
    return os.environ.get("SCHWINGEN_USE_BROWSER", "").lower() in ("1", "true", "yes")


def hole_via_browser(url: str) -> str:
    """Lädt eine Seite mit echtem Headless-Browser (Playwright).

    Für Quellen mit WAF/JS-Schutz (esv.ch) von einer Wohn-IP. Benötigt
    `pip install playwright && playwright install chromium`.
    """
    try:
        from playwright.sync_api import sync_playwright  # type: ignore
    except ImportError as e:  # noqa: BLE001
        raise RuntimeError(
            "SCHWINGEN_USE_BROWSER gesetzt, aber Playwright fehlt. "
            "`pip install playwright && playwright install chromium`."
        ) from e
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        seite = browser.new_page(user_agent=USER_AGENT, locale="de-CH")
        seite.goto(url, wait_until="networkidle", timeout=45000)
        html = seite.content()
        browser.close()
    return html
