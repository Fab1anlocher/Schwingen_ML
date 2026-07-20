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
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        daten = resp.read()
    _letzter_request[host] = time.time()
    return daten if binaer else daten.decode("utf-8", errors="replace")
