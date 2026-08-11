"""Inkrementelles Zeitfenster + Datenqualitätsbericht.

Das Startdatum des täglichen Laufs lag früher als Shell-Heredoc im
Workflow-YAML -- nicht testbar, und ein Fehler dort wäre stillschweigend zu
einem falschen Zeitfenster geworden.
"""
from __future__ import annotations

import json
from datetime import date

from pipeline import config
from pipeline.datenqualitaet import _zeilen, main as bericht_main
from pipeline.fetch_raw import bestimme_seit_datum

HEUTE = date(2026, 8, 11)


class TestBestimmeSeitDatum:
    def test_juengstes_fest_minus_rueckblick(self):
        events = [{"datum": "2026-05-01"}, {"datum": "2026-08-09"}]
        assert bestimme_seit_datum(events, rueckblick_tage=14, heute=HEUTE) == "2026-07-26"

    def test_rueckblick_faengt_nachgetragene_resultate(self):
        """Überlappung > 0, sonst gehen später nachgetragene Feste verloren."""
        events = [{"datum": "2026-08-09"}]
        assert bestimme_seit_datum(events, rueckblick_tage=14, heute=HEUTE) < "2026-08-09"

    def test_ohne_events_faellt_auf_30_tage_zurueck(self):
        assert bestimme_seit_datum([], heute=HEUTE) == "2026-07-12"

    def test_kaputtes_datum_faellt_zurueck_statt_zu_werfen(self):
        assert bestimme_seit_datum([{"datum": "unsinn"}], heute=HEUTE) == "2026-07-12"

    def test_eintraege_ohne_datum_werden_ignoriert(self):
        events = [{"datum": None}, {"datum": "2026-08-09"}, {}]
        assert bestimme_seit_datum(events, rueckblick_tage=14, heute=HEUTE) == "2026-07-26"


class TestDatenqualitaetsbericht:
    def test_markiert_hohe_verlustquote(self):
        text = "\n".join(_zeilen({
            "datenbasis": {"n_gaenge": 50883, "n_schwinger": 1040},
            "datenqualitaet": {"verlustquote": 0.61, "roh_eintraege_verworfen": {"name_nicht_aufloesbar": 148238}},
        }))
        assert "61.0%" in text and "⚠️" in text
        assert "name_nicht_aufloesbar" in text

    def test_gesunde_werte_ohne_warnung(self):
        text = "\n".join(_zeilen({
            "datenbasis": {"n_gaenge": 128768, "n_schwinger": 2899},
            "datenqualitaet": {
                "verlustquote": 0.01, "anteil_unvollstaendiger_gaenge": 0.02,
                "tage_seit_juengstem_fest": 2,
            },
        }))
        assert "⚠️" not in text

    def test_alter_report_ohne_block_bricht_nicht(self):
        text = "\n".join(_zeilen({"datenbasis": {"n_gaenge": 1, "n_schwinger": 1}}))
        assert "Kein Datenqualitätsblock" in text

    def test_cli_meldet_fehlenden_report(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(config, "ARTIFACTS_DIR", tmp_path)
        assert bericht_main() == 1
        assert "zuerst die pipeline" in capsys.readouterr().out.lower()

    def test_cli_rendert_vorhandenen_report(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(config, "ARTIFACTS_DIR", tmp_path)
        (tmp_path / "report.json").write_text(json.dumps({
            "datenbasis": {"n_gaenge": 100, "n_schwinger": 10},
            "datenqualitaet": {"verlustquote": 0.0},
        }), encoding="utf-8")
        assert bericht_main() == 0
        assert "Datenqualität" in capsys.readouterr().out
