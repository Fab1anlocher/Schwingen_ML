"""Tests für die Kantonal-/Gauverband-Statistik (kantone.json + gauverbaende.json).

Deckt den Refactor ab: politische Kantone werden jetzt aus den 29
Gauverband-Buckets abgeleitet statt separat aggregiert -- die Bern-Region
muss dabei exakt die Summe ihrer 6 Gauverbände sein (Nutzerwunsch: Bern
einzeln nach Gauverband statt als ein Blob).
"""
from __future__ import annotations

from pipeline.export import _gauverband_stats, exportiere_kantone
from pipeline.labels import GangResultat
from pipeline.schema import Schwinger


class _FakeElo:
    def __init__(self, werte: dict[str, float]):
        self._werte = werte

    def get(self, sid: str) -> float:
        return self._werte.get(sid, 1500.0)


def _sw(sid, kanton, kranzstatus="kranzer") -> Schwinger:
    return Schwinger(
        id=sid, name=sid, kranzstatus=kranzstatus, kanton=kanton,
        bevorzugte_schwuenge=[], quellen=["schlussgang.ch"],
    )


def test_gauverband_stats_haelt_bernische_regionen_getrennt():
    schwinger = {
        "a": _sw("a", "Emmental"),
        "b": _sw("b", "Oberland"),
        "c": _sw("c", "Emmental"),
        "d": _sw("d", None),  # kein Verband -> nirgends gezaehlt
    }
    elo = _FakeElo({"a": 1600, "b": 1500, "c": 1400, "d": 1500})
    gaenge = [
        GangResultat("ev1", "2024-05-01", "a", "b", "+", 10.0, "-", 8.75, "sieg_a", "kantonal"),
        GangResultat("ev1", "2024-05-01", "c", "d", "-", 9.0, "-", 9.0, "gestellt", "kantonal"),
    ]

    verbaende, _ = _gauverband_stats(schwinger, elo, gaenge)

    assert set(verbaende.keys()) == {"Emmental", "Oberland"}
    assert verbaende["Emmental"]["n_schwinger"] == 2
    assert verbaende["Oberland"]["n_schwinger"] == 1
    assert verbaende["Emmental"]["n_siege"] == 1  # a schlaegt b
    assert verbaende["Oberland"]["n_niederlagen"] == 1
    assert verbaende["Emmental"]["n_gestellt"] == 1  # c vs d (d ohne Verband zaehlt nicht)


def test_politischer_kanton_ist_summe_seiner_gauverbaende(tmp_path, monkeypatch):
    from pipeline import config

    monkeypatch.setattr(config, "ARTIFACTS_DIR", tmp_path / "artifacts")
    monkeypatch.setattr(config, "WEB_PUBLIC_DIR", tmp_path / "web")

    schwinger = {
        "a": _sw("a", "Emmental"),
        "b": _sw("b", "Oberland"),
        "c": _sw("c", "Berner-Jura"),
    }
    elo = _FakeElo({"a": 1600, "b": 1500, "c": 1400})
    gaenge = [
        GangResultat("ev1", "2024-05-01", "a", "b", "+", 10.0, "-", 8.75, "sieg_a", "kantonal"),
    ]

    exportiere_kantone(schwinger, elo, gaenge)

    import json
    kantone = json.loads((tmp_path / "artifacts" / "kantone.json").read_text(encoding="utf-8"))
    gauverbaende = json.loads((tmp_path / "artifacts" / "gauverbaende.json").read_text(encoding="utf-8"))

    bern = next(k for k in kantone["kantone"] if k["kanton"] == "Bern")
    bernische_verbaende = [g for g in gauverbaende["gauverbaende"] if g["kanton"] in {"Emmental", "Oberland", "Berner-Jura"}]

    assert bern["n_schwinger"] == sum(g["n_schwinger"] for g in bernische_verbaende) == 3
    assert bern["n_siege"] == sum(g["n_siege"] for g in bernische_verbaende) == 1
    assert {g["kanton"] for g in bernische_verbaende} == {"Emmental", "Oberland", "Berner-Jura"}
