"""Diagnose der Kranz-Zahlen — beantwortet zwei offene Fragen an der Quelle.

Braucht Netzzugriff auf schlussgang.ch:

    python -m pipeline.diagnose_kranz            # nutzt ein Fest aus events.json
    python -m pipeline.diagnose_kranz --nid 1234 # bestimmtes Fest

**Frage 1: Was bedeutet der Stern in der Statistik-PDF-Kopfzeile?**

Zwei Deutungen sind mit dem Code vereinbar und führen zu völlig verschiedenen
Zahlen:

* **Kranzgewinn an diesem Fest** — dann tragen rund 12-18 % der Teilnehmer
  einen Stern, und zwar zusammenhängend auf den vordersten Rängen.
* **Statusabzeichen des Schwingers** (wie ``field_portrait_wreath_status``,
  wo ``*``/``**``/``***`` Kranzer bzw. Eidgenosse heisst) — dann streuen die
  Sterne über das ganze Rangfeld, und jeder Kranzer trägt an *jedem* Fest
  einen.

Genau das misst ``bewerte_sterne``: Sternquote, Rangverteilung und ob die
Sterne ein lückenloses Rang-Präfix bilden.

**Frage 2: Führt die Porträt-API eine Karriere-Kranzzahl?**

Die App zeigt "N Kränze", gezählt werden aber nur Feste ab 2023. Was man
erwartet, ist die Karriere-Bilanz vom Porträt. Die Feldliste im Scraper
(``fields[node--portrait]``) blendet alles aus, was nicht explizit angefragt
ist — dieses Skript fragt OHNE Filter und listet alle Felder auf.
"""
from __future__ import annotations

import argparse
import json
from urllib.parse import urlencode

from . import config
from .scrape.http import hole
from .scrape.schlussgang_pdf import extrahiere_woerter, pdf_url, tabellen_bloecke
from .scrape.schlussgang_portraet import LIST_API_URL

KRANZ_FEST_TYPEN = {"eidgenoessisch", "berg", "teilverband", "kantonal"}

_BEFUND_TEXT = {
    "kranzgewinn":
        "Stern = KRANZGEWINN an diesem Fest. Die Zaehlung in "
        "run_pipeline._anzahl_kraenze ist damit richtig angesetzt.",
    "statusabzeichen":
        "Stern = STATUSABZEICHEN des Schwingers, kein Kranzgewinn (streut ueber "
        "das Rangfeld bzw. zu viele Traeger). Dann zaehlt _anzahl_kraenze "
        "faktisch besuchte Feste und muss durch die Karriere-Kranzzahl aus dem "
        "Portraet ersetzt werden.",
    "uneindeutig":
        "Uneindeutig — bitte die Beispielzeilen oben von Hand ansehen.",
    "kein_stern_erkannt":
        "Kein einziger Stern erkannt. Entweder hat dieses Fest keine "
        "Kranz-Markierung, oder der Parser findet sie weiterhin nicht.",
    "keine_raenge":
        "Keine Raenge geparst — das PDF-Layout passt nicht zum Parser.",
}


def _rang_zahl(rang) -> int | None:
    ziffern = "".join(c for c in str(rang or "") if c.isdigit())
    return int(ziffern) if ziffern else None


def bewerte_sterne(bloecke: list[dict]) -> dict:
    """Entscheidet aus Rang + Sternverteilung, was der Stern bedeutet.

    Ein Kranz geht an die vordersten Raenge -- die Sterne muessen also ein
    lueckenloses Praefix der Rangliste bilden und rund 12-18 % umfassen. Ein
    Statusabzeichen haengt dagegen am Schwinger und streut ueber das ganze Feld.
    """
    paare = [(_rang_zahl(b.get("rang")), b) for b in bloecke]
    mit_rang = sorted(((r, b) for r, b in paare if r is not None), key=lambda t: t[0])
    n = len(mit_rang)
    if not n:
        return {"n": 0, "befund": "keine_raenge"}

    mit_stern = [(r, b) for r, b in mit_rang if b.get("kranz")]
    quote = len(mit_stern) / n
    if not mit_stern:
        return {"n": n, "n_stern": 0, "quote": 0.0, "befund": "kein_stern_erkannt"}

    schlechtester = max(r for r, _ in mit_stern)
    n_vorne = sum(1 for r, _ in mit_rang if r <= schlechtester)
    lueckenlos = len(mit_stern) == n_vorne

    if lueckenlos and 0.05 <= quote <= 0.30:
        befund = "kranzgewinn"
    elif quote > 0.35 or not lueckenlos:
        befund = "statusabzeichen"
    else:
        befund = "uneindeutig"
    return {
        "n": n,
        "n_stern": len(mit_stern),
        "quote": round(quote, 4),
        "schlechtester_rang_mit_stern": schlechtester,
        "lueckenloses_rang_praefix": lueckenlos,
        "befund": befund,
    }


def _waehle_fest(nid: int | None) -> tuple[int, str]:
    if nid is not None:
        return nid, f"nid {nid}"
    pfad = config.ARTIFACTS_DIR / "events.json"
    events = json.loads(pfad.read_text(encoding="utf-8"))["vergangene"]
    kranzfeste = [e for e in events if e.get("typ") in KRANZ_FEST_TYPEN]
    if not kranzfeste:
        raise SystemExit("Kein Kranzfest in events.json gefunden — --nid angeben.")
    fest = max(kranzfeste, key=lambda e: e["datum"])
    return int(str(fest["id"]).split("-")[-1]), f"{fest['datum']} {fest['name']}"


def frage_1_stern_bedeutung(nid: int, label: str) -> dict:
    print(f"\n=== Frage 1: Bedeutung des Sterns — {label} ===")
    print(f"    {pdf_url(nid)}")
    bloecke = tabellen_bloecke(extrahiere_woerter(hole(pdf_url(nid), binaer=True)))
    res = bewerte_sterne(bloecke)

    print(f"    Teilnehmer im PDF: {res.get('n')}")
    print(f"    davon mit Stern:   {res.get('n_stern', 0)}  ({res.get('quote', 0):.1%})")
    if res.get("schlechtester_rang_mit_stern") is not None:
        print(f"    schlechtester Rang mit Stern: {res['schlechtester_rang_mit_stern']}")
        print(f"    lueckenloses Rang-Praefix:    {res['lueckenloses_rang_praefix']}")

    paare = [(_rang_zahl(b.get("rang")), b) for b in bloecke]
    mit_rang = sorted(((r, b) for r, b in paare if r is not None), key=lambda t: t[0])
    print("    Beispiele (Rang, Stern, Name, Total):")
    for r, b in mit_rang[:25]:
        stern = "*" if b.get("kranz") else " "
        print(f"       {r:<4} {stern}  {b['name']:<30} {b.get('total')}")
    print(f"\n    BEFUND: {_BEFUND_TEXT.get(res['befund'], res['befund'])}")
    return res


def frage_2_portraet_felder(suchname: str) -> None:
    print(f"\n=== Frage 2: Kranz-Felder im Portraet — Suche '{suchname}' ===")
    params = {
        "filter[field_portrait_last_name][value]": suchname,
        "filter[field_portrait_last_name][operator]": "CONTAINS",
        "page[limit]": 1,
        "jsonapi_include": 1,
    }
    roh = json.loads(hole(f"{LIST_API_URL}?{urlencode(params)}"))
    daten = roh.get("data") or []
    if not daten:
        print(f"    Kein Portraet zu '{suchname}' gefunden.")
        return
    felder = daten[0] if isinstance(daten[0], dict) else {}
    print(f"    Portraet: {felder.get('title')}")
    print("    Alle Felder (ohne fields[]-Filter):")
    for schluessel in sorted(felder):
        wert = felder[schluessel]
        text = wert[:120] if isinstance(wert, str) else json.dumps(wert, ensure_ascii=False)[:120]
        print(f"       {schluessel:<45} = {text}")
    treffer = [k for k in felder if any(
        w in k.lower() for w in ("wreath", "kranz", "count", "anzahl", "statistic", "palmares")
    )]
    print("\n    Kandidaten fuer eine Karriere-Kranzzahl:")
    print("      " + (", ".join(treffer) if treffer else "(keine offensichtlichen)"))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Diagnose der Kranz-Zahlen.")
    ap.add_argument("--nid", type=int, default=None, help="Node-ID eines Kranzfests.")
    ap.add_argument("--name", default="Staudenmann", help="Nachname fuer die Portraet-Abfrage.")
    args = ap.parse_args(argv)

    nid, label = _waehle_fest(args.nid)
    try:
        frage_1_stern_bedeutung(nid, label)
    except Exception as e:  # noqa: BLE001
        print(f"    FEHLER: {type(e).__name__}: {e}")
    try:
        frage_2_portraet_felder(args.name)
    except Exception as e:  # noqa: BLE001
        print(f"    FEHLER: {type(e).__name__}: {e}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
