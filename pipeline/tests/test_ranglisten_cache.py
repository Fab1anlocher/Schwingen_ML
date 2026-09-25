"""Nachladen der Schlussranglisten in artifacts/raw/ranglisten.json."""
from __future__ import annotations

import json

import pipeline.scrape.schlussgang_resultate as sr


def _events(*nids):
    return [{"id": f"schlussgang-{n}", "nid": n, "datum": "2025-06-01", "name": f"Fest {n}"} for n in nids]


def test_nur_fehlende_werden_geladen_fehler_nicht_taeglich_erneut(tmp_path, monkeypatch):
    geladen = []

    def lade(event):
        geladen.append(event["nid"])
        if event["nid"] == 3:
            raise ValueError("kaputt")
        return [{"name": "A B", "punkte": 57.0, "kranz": True}]

    monkeypatch.setattr(sr, "lade_rangliste", lade)
    pfad = tmp_path / "ranglisten.json"
    daten = sr.ergaenze_ranglisten(pfad, _events(1, 2, 3))
    assert geladen == [1, 2, 3] and "fehler" in daten["schlussgang-3"]

    geladen.clear()
    sr.ergaenze_ranglisten(pfad, _events(1, 2, 3, 4))
    assert geladen == [4], "Cache und vermerkte Fehler werden nicht erneut geladen"

    geladen.clear()
    sr.ergaenze_ranglisten(pfad, _events(1, 2, 3, 4), neu_laden={"schlussgang-2"})
    assert geladen == [2], "frisch geladene Feste werden neu geholt (nachgetragene Resultate)"
    assert json.loads(pfad.read_text())["ranglisten"]["schlussgang-1"]["eintraege"][0]["kranz"]


def test_fehlende_url_wird_aus_der_api_liste_nachgetragen(monkeypatch):
    """Älterer Cache ohne rangliste_url; ESAF 2025 folgt nicht dem Muster."""
    monkeypatch.setattr(sr, "scrape_events", lambda *a, **k: [
        {"id": "schlussgang-21055", "rangliste_url": "https://www.schlussgang.ch/x/Schlussrangliste.pdf"}])
    events = _events(21055, 7) + [{"id": "schlussgang-8", "nid": 8, "datum": "2025-01-01",
                                   "rangliste_url": "https://bereits"}]
    n = sr.vervollstaendige_rangliste_urls(events, schon_geladen={"schlussgang-7"})
    assert n == 1 and events[0]["rangliste_url"].endswith("Schlussrangliste.pdf")
    assert "rangliste_url" not in events[1]


def test_url_muster_als_rueckfall():
    assert sr.rangliste_url_fallback(51612).endswith("/event-ranking-list/51612-final.pdf")
