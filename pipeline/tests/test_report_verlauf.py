"""Verlauf der Modellgüte (Roadmap T1): ein Eintrag je Tag und Modellstand, Warnung bei Rückschritt."""
from __future__ import annotations

import json

from pipeline import config
from pipeline.export import ergaenze_verlauf, verlauf_warnung


def _report(datum, ll, typ="gbm", version=3, holdout=2026):
    return {"erstellt": f"{datum}T04:00:00+00:00", "modell_typ": typ, "merkmal_version": version,
            "holdout_jahr": holdout, "modell": {"log_loss": ll, "accuracy": 0.68},
            "datenbasis": {"n_gaenge": 130000}, "n_test": 36000}


def _eintrag(datum, ll, **kw):
    from pipeline.export import verlauf_eintrag
    return verlauf_eintrag(_report(datum, ll, **kw))


def test_ein_eintrag_je_tag_der_juengste_zaehlt(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ARTIFACTS_DIR", tmp_path / "a")
    monkeypatch.setattr(config, "WEB_PUBLIC_DIR", tmp_path / "w")
    ergaenze_verlauf(_report("2026-09-25", 0.75))
    ergaenze_verlauf(_report("2026-09-26", 0.74))
    info = ergaenze_verlauf(_report("2026-09-26", 0.72))
    laeufe = json.loads((tmp_path / "a" / "report_verlauf.json").read_text())["laeufe"]
    assert [(l["datum"], l["log_loss"]) for l in laeufe] == [("2026-09-25", 0.75), ("2026-09-26", 0.72)]
    assert info["n_laeufe"] == 2 and (tmp_path / "w" / "report_verlauf.json").exists()


def test_modellwechsel_am_selben_tag_behaelt_den_punkt_davor(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ARTIFACTS_DIR", tmp_path / "a")
    monkeypatch.setattr(config, "WEB_PUBLIC_DIR", tmp_path / "w")
    ergaenze_verlauf(_report("2026-09-24", 0.83, typ="lr", version=1))
    ergaenze_verlauf(_report("2026-09-25", 0.74, typ="lr"))
    ergaenze_verlauf(_report("2026-09-25", 0.72))
    ergaenze_verlauf(_report("2026-09-25", 0.721))  # gleicher Stand: ersetzt
    laeufe = json.loads((tmp_path / "a" / "report_verlauf.json").read_text())["laeufe"]
    assert [(l["datum"], l["modell_typ"], l["log_loss"]) for l in laeufe] == [
        ("2026-09-24", "lr", 0.83), ("2026-09-25", "lr", 0.74), ("2026-09-25", "gbm", 0.721)]


def test_warnung_nur_bei_rueckschritt_gegenueber_vergleichbaren_laeufen():
    ruhig = [_eintrag(f"2026-09-{t:02d}", 0.720 + 0.001 * (t % 2)) for t in range(1, 8)]
    assert verlauf_warnung(ruhig + [_eintrag("2026-09-10", 0.725)]) is None
    assert "über dem Median" in verlauf_warnung(ruhig + [_eintrag("2026-09-10", 0.735)])
    # Modellwechsel oder neue Saison ist kein Rückschritt: nichts Vergleichbares davor.
    assert verlauf_warnung(ruhig + [_eintrag("2026-09-10", 0.80, typ="lr")]) is None
    assert verlauf_warnung(ruhig + [_eintrag("2027-06-01", 0.80, holdout=2027)]) is None
