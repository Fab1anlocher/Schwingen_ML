"""Tests für das Sicherheitsnetz gegen stillen Datenverlust.

Hintergrund: der tägliche Lauf baut auf dem Rohdaten-Cache auf. Die alte
Prüfung verglich nur "Gänge neu vs. Gänge zuvor" und konnte deshalb nicht
unterscheiden, ob der Cache leer war oder die Verarbeitung kaputt. Sie hat den
Workflow 20 Tage in Folge blockiert, obwohl der Download funktionierte.
Jetzt werden Verarbeitung (Verlustquote) und Abdeckung (Cache) getrennt geprüft.
"""
from __future__ import annotations

import json
from collections import Counter

import pytest

from pipeline import config, run_pipeline
from pipeline.scrape import IngestBericht


def _bericht(*, gesamt: int, uebernommen: int) -> IngestBericht:
    b = IngestBericht()
    b.n_roh_gesamt = gesamt
    b.n_roh_uebernommen = uebernommen
    b.verworfen = Counter({"name_nicht_aufloesbar": gesamt - uebernommen})
    return b


def _schreibe_report(pfad, *, n_gaenge: int, roh_gelesen: int | None = None) -> None:
    obj = {"datenbasis": {"n_gaenge": n_gaenge}}
    if roh_gelesen is not None:
        obj["datenqualitaet"] = {"roh_eintraege_gelesen": roh_gelesen}
    pfad.write_text(json.dumps(obj), encoding="utf-8")


def test_hohe_verlustquote_bricht_ab(tmp_path, monkeypatch):
    """Der eigentliche Produktionsfehler: Download ok, Namensauflösung kaputt."""
    monkeypatch.setattr(config, "ARTIFACTS_DIR", tmp_path)
    bericht = _bericht(gesamt=243_479, uebernommen=95_241)  # real beobachtet: 61 % Verlust
    with pytest.raises(RuntimeError, match="verworfen"):
        run_pipeline._pruefe_datenqualitaet("scrape", bericht, 50_883)


def test_kleiner_verlust_ist_ok(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ARTIFACTS_DIR", tmp_path)
    _schreibe_report(tmp_path / "report.json", n_gaenge=120_000, roh_gelesen=240_000)
    bericht = _bericht(gesamt=243_000, uebernommen=240_000)
    run_pipeline._pruefe_datenqualitaet("scrape", bericht, 121_000)  # kein Fehler


def test_geschrumpfter_cache_bricht_ab(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ARTIFACTS_DIR", tmp_path)
    _schreibe_report(tmp_path / "report.json", n_gaenge=120_000, roh_gelesen=240_000)
    bericht = _bericht(gesamt=3_000, uebernommen=2_950)  # Cache weg, nur Tagesfenster
    with pytest.raises(RuntimeError, match="Abdeckung"):
        run_pipeline._pruefe_datenqualitaet("scrape", bericht, 1_400)


def test_verarbeitungsfehler_bei_intaktem_cache_bricht_ab(tmp_path, monkeypatch):
    """Rohabdeckung stimmt, es kommen trotzdem kaum Gänge an."""
    monkeypatch.setattr(config, "ARTIFACTS_DIR", tmp_path)
    _schreibe_report(tmp_path / "report.json", n_gaenge=120_000, roh_gelesen=240_000)
    bericht = _bericht(gesamt=245_000, uebernommen=244_000)
    with pytest.raises(RuntimeError, match="Verarbeitungsfehler"):
        run_pipeline._pruefe_datenqualitaet("scrape", bericht, 10_000)


def test_kein_altes_report_kein_abbruch(tmp_path, monkeypatch):
    """Erstlauf (z.B. nach vollem Refetch) darf nicht an einem Vergleich scheitern."""
    monkeypatch.setattr(config, "ARTIFACTS_DIR", tmp_path)
    run_pipeline._pruefe_datenqualitaet("scrape", _bericht(gesamt=1000, uebernommen=990), 400)


def test_ohne_volumenpruefung_erlaubt_neuaufbau(tmp_path, monkeypatch):
    """--ohne-volumenpruefung hebt den Vorlauf-Vergleich auf, nicht die Verlustprüfung."""
    monkeypatch.setattr(config, "ARTIFACTS_DIR", tmp_path)
    _schreibe_report(tmp_path / "report.json", n_gaenge=120_000, roh_gelesen=240_000)
    bericht = _bericht(gesamt=3_000, uebernommen=2_950)
    run_pipeline._pruefe_datenqualitaet("scrape", bericht, 1_400, streng=False)  # kein Fehler
    with pytest.raises(RuntimeError):
        run_pipeline._pruefe_datenqualitaet(
            "scrape", _bericht(gesamt=1000, uebernommen=100), 400, streng=False
        )


def test_synth_quelle_wird_nie_geprueft(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ARTIFACTS_DIR", tmp_path)
    _schreibe_report(tmp_path / "report.json", n_gaenge=125_553, roh_gelesen=240_000)
    run_pipeline._pruefe_datenqualitaet("synth", None, 5)  # synth ist nicht betroffen
