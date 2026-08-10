"""Erreichbarkeits-Sonde für Datenquellen (aus GitHub Actions).

Testet, welche Schwingen-Quellen vom Cloud-Runner (Rechenzentrums-IP) OHNE
403/WAF erreichbar sind — Grundlage für die Wahl der automatisch scrapebaren
Quelle. Tolerant (exit 0), druckt Status/Content-Type/Grösse in die Logs.
"""
from __future__ import annotations

import urllib.request
import urllib.error

UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

ZIELE = [
    # schlussgang.ch (ursprüngliche Quelle: HTML + PDF-Backend)
    "https://schlussgang.ch/",
    "https://www.schlussgang.ch/resultate",
    "https://backend-api.schlussgang.ch/sites/default/files/event-ranking-list/52026-statistic-final.pdf",
    "https://backend-api.schlussgang.ch/sites/default/files/event-ranking-list/21068-final.pdf",
    "https://backend.schlussgang.ch/sites/default/files/event-ranking-list/22403-final.pdf",
    # zwilch.ch (grosse Historie)
    "https://zwilch.ch/",
    # SRF (Quer-Validierung)
    "https://www.srf.ch/sport/schwingen",
]


def probe(url: str) -> None:
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "text/html,application/xhtml+xml,application/pdf,*/*;q=0.8",
        "Accept-Language": "de-CH,de;q=0.9",
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read(2048)
            ct = resp.headers.get("Content-Type", "?")
            clen = resp.headers.get("Content-Length", "?")
            print(f"  OK  {resp.status}  {ct}  len={clen}  first={body[:16]!r}")
            print(f"      -> ERREICHBAR: {url}")
    except urllib.error.HTTPError as e:
        print(f"  {e.code} {e.reason}  (blockiert/fehlt): {url}")
    except Exception as e:  # noqa: BLE001
        print(f"  Fehler {type(e).__name__}: {e}: {url}")


def main():
    print("=== Datenquellen-Erreichbarkeit vom Cloud-Runner ===")
    for z in ZIELE:
        print(f"\n>>> {z}")
        probe(z)


if __name__ == "__main__":
    main()
