"""Tests für "ähnliche Schwinger" (KNN über das Porträt-Profil)."""
from __future__ import annotations

from pipeline.clustering import MIN_KANDIDATEN, N_AEHNLICHSTE, berechne_aehnlichste
from pipeline.schema import Schwinger

REFERENZ_JAHR = 2026


class _FakeEloModell:
    """Minimaler Ersatz für EloModell in Tests: konstantes Elo, keine Erfahrung,
    ausser explizit override."""

    def __init__(self, elo: dict[str, float] | None = None, gaenge: dict[str, int] | None = None):
        self._elo = elo or {}
        self.gaenge_gezaehlt = gaenge or {}

    def get(self, sid: str) -> float:
        return self._elo.get(sid, 1500.0)


def _sw(
    sid: str,
    gewicht: float | None,
    groesse: float | None,
    schwuenge=None,
    jahrgang=None,
    kranzstatus="kein",
) -> Schwinger:
    return Schwinger(
        id=sid, name=sid, gewicht_kg=gewicht, groesse_cm=groesse,
        jahrgang=jahrgang, kranzstatus=kranzstatus,
        bevorzugte_schwuenge=schwuenge or [], quellen=["schlussgang.ch"],
    )


def test_zu_wenig_profildaten_gibt_none():
    schwinger = {f"s{i}": _sw(f"s{i}", 90.0, 180.0) for i in range(MIN_KANDIDATEN - 1)}
    assert berechne_aehnlichste(schwinger, _FakeEloModell(), REFERENZ_JAHR) is None


def test_ohne_gewicht_oder_groesse_zaehlt_nicht_als_kandidat():
    schwinger = {
        "a": _sw("a", None, 180.0),
        "b": _sw("b", 90.0, None),
        **{f"s{i}": _sw(f"s{i}", 80.0 + i, 170.0 + i) for i in range(MIN_KANDIDATEN)},
    }
    ergebnis = berechne_aehnlichste(schwinger, _FakeEloModell(), REFERENZ_JAHR)
    assert "a" not in ergebnis["aehnlichste"] and "b" not in ergebnis["aehnlichste"]


def test_naechste_nachbarn_bleiben_in_der_eigenen_gruppe():
    leicht = {f"leicht{i}": _sw(f"leicht{i}", 70.0 + i * 0.7, 165.0 + i * 0.6, ["Kurz"])
              for i in range(20)}
    schwer = {f"schwer{i}": _sw(f"schwer{i}", 130.0 + i * 0.7, 195.0 + i * 0.6, ["Brienzer"])
              for i in range(20)}
    schwinger = {**leicht, **schwer}

    ergebnis = berechne_aehnlichste(schwinger, _FakeEloModell(), REFERENZ_JAHR)

    assert ergebnis["merkmale"][:7] == [
        "gewicht_kg", "groesse_cm", "kompaktheit", "elo", "erfahrung", "alter", "kranzstatus",
    ]
    aehnlichste = ergebnis["aehnlichste"]
    assert set(aehnlichste.keys()) == set(schwinger.keys())
    for sid in leicht:
        treffer = aehnlichste[sid]
        assert 1 <= len(treffer) <= N_AEHNLICHSTE
        assert all(t["schwinger_id"] in leicht for t in treffer)
        assert all(t["schwinger_id"] != sid for t in treffer)  # nie sich selbst
        assert all(0.0 < t["score"] <= 1.0 for t in treffer)
        scores = [t["score"] for t in treffer]
        assert scores == sorted(scores, reverse=True)


def test_schwungnamen_werden_gross_kleinschreibung_normalisiert():
    # Rohdaten schreiben denselben Schwung uneinheitlich ("innerer Haken" /
    # "Innerer Haken") -- ohne Normalisierung wuerden das zwei Spalten,
    # jede unter der Haeufigkeitsschwelle, obwohl zusammen weit drüber.
    a = {f"a{i}": _sw(f"a{i}", 90.0 + i, 180.0 + i, ["innerer Haken"]) for i in range(6)}
    b = {f"b{i}": _sw(f"b{i}", 90.0 + i, 180.0 + i, ["Innerer Haken"]) for i in range(6)}
    schwinger = {**a, **b}

    ergebnis = berechne_aehnlichste(schwinger, _FakeEloModell(), REFERENZ_JAHR)

    assert "Innerer Haken" in ergebnis["merkmale"]
    assert "innerer Haken" not in ergebnis["merkmale"]


def test_elo_und_kranzstatus_trennen_auch_bei_gleicher_physis():
    staerker = {f"stark{i}": _sw(f"stark{i}", 95.0 + i * 0.1, 182.0 + i * 0.1,
                                 jahrgang=1990 + i % 5, kranzstatus="eidgenosse")
                for i in range(20)}
    schwaecher = {f"schwach{i}": _sw(f"schwach{i}", 95.0 + i * 0.1, 182.0 + i * 0.1,
                                     jahrgang=2000 + i % 5, kranzstatus="kein")
                  for i in range(20)}
    schwinger = {**staerker, **schwaecher}
    elo = {sid: 2100.0 for sid in staerker}
    elo.update({sid: 1300.0 for sid in schwaecher})
    elo_modell = _FakeEloModell(elo=elo, gaenge={**{s: 300 for s in staerker},
                                                 **{s: 20 for s in schwaecher}})

    ergebnis = berechne_aehnlichste(schwinger, elo_modell, REFERENZ_JAHR)

    for sid in staerker:
        assert all(t["schwinger_id"] in staerker for t in ergebnis["aehnlichste"][sid])
