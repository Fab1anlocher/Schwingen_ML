"""Tests für das Sicherheitsnetz gegen einen eingebrochenen Rohdaten-Fetch.

Hintergrund: der taegliche Update-Workflow laedt Rohdaten nur inkrementell
fuer ein kurzes Zeitfenster (artifacts/raw/ wird nicht zwischen CI-Laeufen
persistiert). Faellt dieser Fetch auf ein winziges Zeitfenster zurueck, darf
run_pipeline das produktive, auf der vollen Historie trainierte Modell nicht
stillschweigend durch ein auf wenigen hundert Gaengen trainiertes ersetzen.
"""
from __future__ import annotations

import json

import pytest

from pipeline import config, run_pipeline


def _schreibe_report(pfad, n_gaenge: int) -> None:
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(json.dumps({"datenbasis": {"n_gaenge": n_gaenge}}), encoding="utf-8")


def test_kein_altes_report_kein_abbruch(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ARTIFACTS_DIR", tmp_path)
    run_pipeline._pruefe_datenvolumen("scrape", 10)  # kein Fehler -> ok


def test_drastischer_einbruch_bricht_ab(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ARTIFACTS_DIR", tmp_path)
    _schreibe_report(tmp_path / "report.json", n_gaenge=125_553)

    with pytest.raises(RuntimeError, match="Datenvolumen eingebrochen"):
        run_pipeline._pruefe_datenvolumen("scrape", 987)


def test_normale_taegliche_zunahme_kein_abbruch(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ARTIFACTS_DIR", tmp_path)
    _schreibe_report(tmp_path / "report.json", n_gaenge=125_553)

    run_pipeline._pruefe_datenvolumen("scrape", 125_600)  # kein Fehler -> ok


def test_synth_quelle_wird_nie_geprueft(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ARTIFACTS_DIR", tmp_path)
    _schreibe_report(tmp_path / "report.json", n_gaenge=125_553)

    run_pipeline._pruefe_datenvolumen("synth", 5)  # kein Fehler -> ok, synth ist nicht betroffen
