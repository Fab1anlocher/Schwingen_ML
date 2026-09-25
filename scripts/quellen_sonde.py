"""Einmalige Quellen-Diagnose, Runde 3 (läuft auf einem GitHub-Runner).

Holt eine Stichprobe echter Schlussranglisten-PDFs (verschiedene Jahre,
Festtypen, Sonderpfade) und gibt sie base64-kodiert ins Log aus -- als
Testmaterial für den Parser, der lokal entwickelt wird (schlussgang.ch ist
aus der Entwicklungsumgebung nicht erreichbar).

Höflich: robots.txt geprüft, 2 s Abstand je Host (http.hole).
"""
from __future__ import annotations

import base64
import gzip
import json
import sys
from urllib.parse import urlencode

sys.path.insert(0, ".")
from pipeline.scrape.http import hole  # noqa: E402

API = "https://backend-api.schlussgang.ch/jsonapi/node/event"
BASIS = "https://www.schlussgang.ch"

feste = []
offset = 0
while True:
    params = {
        "filter[state][condition][path]": "field_event_state",
        "filter[state][condition][value]": "finished",
        "filter[typ][condition][path]": "field_event_type",
        "filter[typ][condition][value]": "Aktivschwinger",
        "filter[datum][condition][path]": "field_event_date",
        "filter[datum][condition][value]": "2023-01-01",
        "filter[datum][condition][operator]": ">=",
        "sort": "-field_event_date",
        "page[limit]": 50,
        "page[offset]": offset,
        "include": "field_final_ranking_pdf,field_category",
        "fields[node--event]": "drupal_internal__nid,title,field_event_date,field_final_ranking_pdf,field_category",
        "fields[file--file]": "uri",
        "fields[taxonomy_term--event_tags]": "name",
    }
    daten = json.loads(hole(f"{API}?{urlencode(params)}"))
    inc = {i["id"]: i["attributes"] for i in daten.get("included", [])}
    for item in daten["data"]:
        a = item["attributes"]
        rel = (item["relationships"].get("field_final_ranking_pdf") or {}).get("data")
        kat = (item["relationships"].get("field_category") or {}).get("data")
        url = (inc.get(rel["id"]) or {}).get("uri", {}).get("url") if rel else None
        feste.append({"nid": a["drupal_internal__nid"], "datum": a["field_event_date"],
                      "titel": a["title"], "url": url,
                      "kategorie": (inc.get(kat["id"]) or {}).get("name") if kat else None})
    if len(daten["data"]) < 50 or offset > 1500:
        break
    offset += 50

print("KATEGORIEN:", sorted({f["kategorie"] for f in feste if f["kategorie"]}))
auswahl: dict[str, dict] = {}
for f in feste:
    if not f["url"]:
        continue
    k = f["kategorie"] or "?"
    jahr = f["datum"][:4]
    if f"{k}-{jahr}" not in auswahl and len(auswahl) < 14:
        auswahl[f"{k}-{jahr}"] = f
    if not f["url"].endswith("-final.pdf"):
        auswahl[f"sonder-{f['nid']}"] = f

for schluessel, f in auswahl.items():
    pdf = hole(BASIS + f["url"], binaer=True)
    kodiert = base64.b64encode(gzip.compress(pdf)).decode()
    print(f"PDFSTART {json.dumps({**f, 'schluessel': schluessel})}")
    for i in range(0, len(kodiert), 4000):
        print("PDF " + kodiert[i:i + 4000])
    print("PDFENDE")
