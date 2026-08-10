"""Discovery-Sonde: automatische Fest-ID-Ermittlung für schlussgang.ch."""
from __future__ import annotations

import re
import urllib.request

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/124.0.0.0 Safari/537.36")


def get(url: str) -> tuple[int, str]:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001
        return -1, f"{type(e).__name__}: {e}"


def main():
    # 1) Sitemaps
    for u in ["https://schlussgang.ch/sitemap.xml",
              "https://www.schlussgang.ch/sitemap.xml",
              "https://backend.schlussgang.ch/sitemap.xml",
              "https://schlussgang.ch/robots.txt"]:
        code, body = get(u)
        ev = len(re.findall(r"/event/", body)) if code == 200 else 0
        sm = re.findall(r"<loc>([^<]+sitemap[^<]*)</loc>", body)[:5] if code == 200 else []
        print(f">>> {u} -> {code}  /event-Vorkommen={ev}  sub-sitemaps={sm}")
        if code == 200 and "sitemap" in u:
            print("    erste loc-Einträge:", re.findall(r"<loc>([^<]+)</loc>", body)[:5])

    # 2) Event-Seite: statistic-final-ID extrahieren
    for u in ["https://backend.schlussgang.ch/event/nordostschweizer-schwingfest-guettingen-2026",
              "https://www.schlussgang.ch/event/nordostschweizer-schwingfest-guettingen-2026"]:
        code, body = get(u)
        ids = re.findall(r"event-ranking-list/(\d+)-statistic-final", body)
        anyids = re.findall(r"event-ranking-list/(\d+)-", body)
        print(f">>> {u} -> {code}  statistic-ids={sorted(set(ids))[:5]}  any={sorted(set(anyids))[:5]}")

    # 3) Mögliche JSON-API (Drupal jsonapi)
    for u in ["https://backend-api.schlussgang.ch/jsonapi",
              "https://backend-api.schlussgang.ch/api/events",
              "https://backend.schlussgang.ch/jsonapi/node/event?page[limit]=3"]:
        code, body = get(u)
        print(f">>> {u} -> {code}  len={len(body)}  head={body[:120]!r}")


if __name__ == "__main__":
    main()
