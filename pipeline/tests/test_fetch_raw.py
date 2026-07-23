"""Tests für fetch_raw.py: ein ESV-Fehler darf den Lauf nicht abbrechen.

Hintergrund: esv.ch blockiert Anfragen von GitHub-Actions-Runnern (403,
IP-basiert), was den täglichen Update-Workflow abstürzen liess -- noch
bevor die wichtigere "events"-Quelle (neue Feste/Gänge, NFR-1) geladen
wurde. esv_statistiken.json wird von keiner anderen Pipeline-Stufe
gelesen, ein Fehlschlag dort ist also nie kritisch für --source scrape.
"""
from __future__ import annotations

from pipeline import fetch_raw


def test_esv_fehler_bricht_lauf_nicht_ab(monkeypatch, capsys):
    def _kaputt(*args, **kwargs):
        raise RuntimeError("403 Forbidden (simuliert)")

    monkeypatch.setattr(fetch_raw, "scrape_esv_statistiken", _kaputt)

    rc = fetch_raw.main(["--sources", "esv"])

    assert rc == 0
    ausgabe = capsys.readouterr().out
    assert "[esv] übersprungen" in ausgabe
