"""Einmalige Quellen-Diagnose, Runde 2 (läuft auf einem GitHub-Runner).

Befund Runde 1: jedes Fest führt eine Schlussrangliste (field_final_ranking_pdf,
<nid>-final.pdf) mit Wohnort und Schwingklub JEDES Teilnehmers.

Fragen jetzt:
  1. Abdeckung: wie viele Feste 2023-2026 haben eine Schlussrangliste?
  2. Layout: Wortpositionen (x0) von Kopf- und Datenzeilen -- Wohnort und
     Schwingklub lassen sich im Fliesstext nicht trennen ("Appenzell Schlatt
     Appenzell"), nur über die Spaltenposition.
  3. Ist das Layout über Jahre und Festtypen gleich?

Höflich: robots.txt geprüft, 2 s Abstand je Host (http.hole).
"""
from __future__ import annotations

import collections
import io
import json
import sys
from urllib.parse import urlencode

sys.path.insert(0, ".")
from pipeline.scrape.http import hole  # noqa: E402

API = "https://backend-api.schlussgang.ch/jsonapi/node/event"
BASIS = "https://www.schlussgang.ch"

print("## 1. Abdeckung Schlussrangliste 2023-2026 (Aktivschwinger, abgeschlossen)")
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
        "include": "field_final_ranking_pdf",
        "fields[node--event]": "drupal_internal__nid,title,field_event_date,field_final_ranking_pdf,field_final_statistic_pdf",
        "fields[file--file]": "filename,uri",
    }
    daten = json.loads(hole(f"{API}?{urlencode(params)}"))
    dateien = {i["id"]: i["attributes"] for i in daten.get("included", [])}
    for item in daten["data"]:
        a = item["attributes"]
        rel = (item["relationships"].get("field_final_ranking_pdf") or {}).get("data")
        stat = (item["relationships"].get("field_final_statistic_pdf") or {}).get("data")
        datei = dateien.get(rel["id"]) if rel else None
        feste.append({
            "nid": a["drupal_internal__nid"], "datum": a["field_event_date"], "titel": a["title"],
            "rangliste": (datei or {}).get("uri", {}).get("url") if datei else None,
            "statistik": bool(stat),
        })
    if len(daten["data"]) < 50 or offset > 1500:
        break
    offset += 50

nach_jahr = collections.defaultdict(lambda: [0, 0, 0])
for f in feste:
    j = nach_jahr[f["datum"][:4]]
    j[0] += 1
    j[1] += bool(f["rangliste"])
    j[2] += f["statistik"]
for jahr in sorted(nach_jahr):
    n, r, s = nach_jahr[jahr]
    print(f"- {jahr}: {n} Feste, Schlussrangliste {r}, Statistik {s}")
namen = collections.Counter((f["rangliste"] or "").rsplit("-", 1)[-1] for f in feste if f["rangliste"])
print(f"- Dateinamen-Endungen: {dict(namen)}")


def layout(fest: dict, n_zeilen: int = 14) -> None:
    import pdfplumber
    url = BASIS + fest["rangliste"]
    print(f"\n### {fest['titel']} ({fest['datum']}) {url}")
    with pdfplumber.open(io.BytesIO(hole(url, binaer=True))) as pdf:
        print(f"  Seiten: {len(pdf.pages)}, Breite {pdf.pages[0].width:.0f}")
        woerter = pdf.pages[0].extract_words(keep_blank_chars=False, use_text_flow=False)
        zeilen = collections.defaultdict(list)
        for w in woerter:
            zeilen[round(w["top"] / 3)].append(w)
        for i, key in enumerate(sorted(zeilen)):
            if i >= n_zeilen:
                break
            ws = sorted(zeilen[key], key=lambda w: w["x0"])
            print("  " + " | ".join(f"{w['text']}@{w['x0']:.0f}" for w in ws))
        # letzte Seite, letzte Zeilen (Fusszeile / Ende der Tabelle)
        letzte = pdf.pages[-1].extract_text() or ""
        print("  … letzte Zeilen: " + " // ".join(letzte.splitlines()[-4:]))


mit = [f for f in feste if f["rangliste"]]
if mit:
    stichprobe = {}
    for f in mit:
        t = f["titel"].lower()
        if "eidgen" in t and "eidg" not in stichprobe:
            stichprobe["eidg"] = f
        elif "kantonal" in t and "kant" not in stichprobe:
            stichprobe["kant"] = f
    stichprobe["aeltestes"] = mit[-1]
    stichprobe["neuestes"] = mit[0]
    for f in stichprobe.values():
        layout(f)
