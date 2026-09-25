"""Einmalige Quellen-Diagnose (läuft auf einem GitHub-Runner, nicht lokal).

Fragen:
  1. Sperrt esv.ch (inkl. Verbands-Subdomains) Cloud-IPs weiterhin?
  2. Welche Felder/Dateien führt ein Fest in der schlussgang.ch-JSON:API?
  3. Gibt es neben der Statistik-PDF eine vollständige Rangliste (Jahrgang,
     Klub je Teilnehmer)?

Höflich: wenige Anfragen, robots.txt geprüft, 2 s Abstand je Host (http.hole).
"""
from __future__ import annotations

import io
import json
import sys
import time
import urllib.error
import urllib.request
from urllib.parse import urlencode

sys.path.insert(0, ".")
from pipeline.config import USER_AGENT  # noqa: E402
from pipeline.scrape.http import darf_abrufen, hole  # noqa: E402

API = "https://backend-api.schlussgang.ch/jsonapi/node/event"


def status(url: str, methode: str = "GET") -> str:
    if not darf_abrufen(url):
        return "robots.txt verbietet"
    time.sleep(2)
    req = urllib.request.Request(url, method=methode, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return f"{r.status} {r.headers.get('content-type', '')} {r.headers.get('content-length', '')}"
    except urllib.error.HTTPError as e:
        return f"HTTP {e.code} {e.headers.get('server', '')}"
    except Exception as e:  # noqa: BLE001
        return f"{type(e).__name__}: {e}"


def kurz(v, n=140):
    s = json.dumps(v, ensure_ascii=False) if not isinstance(v, str) else v
    return s if len(s) <= n else s[:n] + "…"


print("## 1. Erreichbarkeit von Cloud-IP (GitHub-Runner)")
for url in ("https://esv.ch/robots.txt", "https://esv.ch/ranglisten/",
            "https://zksv.esv.ch/agenda/", "https://nosv.esv.ch/agenda/",
            "https://www.schlussgang.ch/robots.txt"):
    print(f"- {url}: {status(url)}")

print("\n## 2. Ein abgeschlossenes Fest, alle Felder")
params = {
    "filter[state][condition][path]": "field_event_state",
    "filter[state][condition][value]": "finished",
    "filter[typ][condition][path]": "field_event_type",
    "filter[typ][condition][value]": "Aktivschwinger",
    "sort": "-field_event_date",
    "page[limit]": 3,
}
daten = json.loads(hole(f"{API}?{urlencode(params)}"))
for item in daten["data"]:
    a = item["attributes"]
    print(f"\n### nid {a.get('drupal_internal__nid')} — {a.get('title')} ({a.get('field_event_date')})")
    for k in sorted(a):
        if k.startswith("field_") or k in ("title", "path"):
            print(f"  attr {k}: {kurz(a[k])}")
    for k, rel in sorted((item.get("relationships") or {}).items()):
        d = rel.get("data")
        print(f"  rel  {k}: {kurz(d, 200)}")
        # Datei-/Medien-Beziehungen auflösen
        if d and any(t in json.dumps(d) for t in ("file--file", "media--")):
            link = (rel.get("links") or {}).get("related", {}).get("href")
            if link:
                try:
                    inhalt = json.loads(hole(link))
                    eintraege = inhalt["data"] if isinstance(inhalt["data"], list) else [inhalt["data"]]
                    for e in eintraege:
                        ea = e.get("attributes", {})
                        print(f"       -> {e.get('type')}: {ea.get('filename')} {kurz(ea.get('uri'), 200)}")
                except Exception as ex:  # noqa: BLE001
                    print(f"       -> Fehler: {ex}")

nid = daten["data"][0]["attributes"]["drupal_internal__nid"]
print(f"\n## 3. Kandidaten für eine Rangliste (nid {nid})")
basis = "https://www.schlussgang.ch/sites/default/files/event-ranking-list"
gefunden = []
for suffix in ("statistic-final", "ranking-final", "rangliste-final", "ranking-list-final",
               "ranking", "rangliste", "result-final", "results-final", "final"):
    url = f"{basis}/{nid}-{suffix}.pdf"
    s = status(url, "HEAD")
    print(f"- {nid}-{suffix}.pdf: {s}")
    if s.startswith("200") and suffix != "statistic-final":
        gefunden.append(url)

for url in gefunden[:2]:
    print(f"\n### Textauszug {url}")
    import pdfplumber
    with pdfplumber.open(io.BytesIO(hole(url, binaer=True))) as pdf:
        text = (pdf.pages[0].extract_text() or "").splitlines()
    for zeile in text[:60]:
        print("   " + zeile)
