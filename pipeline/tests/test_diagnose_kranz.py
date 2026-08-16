"""Die Auswertung, die entscheidet, was der Stern in der Statistik-PDF bedeutet.

Ohne diese Unterscheidung ist die Kranz-Zahl nicht interpretierbar: dieselbe
Markierung heisst je nach Deutung "Kranz an diesem Fest" oder "Kranzstatus des
Schwingers" -- und im zweiten Fall zaehlt die Pipeline besuchte Feste.
"""
from __future__ import annotations

from pipeline.diagnose_kranz import bewerte_sterne


def _feld(n: int, stern_raenge: set[int]) -> list[dict]:
    return [
        {"rang": str(r), "name": f"Schwinger {r}", "total": 57.0, "kranz": r in stern_raenge}
        for r in range(1, n + 1)
    ]


def test_sterne_auf_den_vorderen_raengen_sind_kranzgewinne():
    # 100 Teilnehmer, Raenge 1-15 mit Stern: klassische Kranzverteilung.
    res = bewerte_sterne(_feld(100, set(range(1, 16))))
    assert res["befund"] == "kranzgewinn"
    assert res["quote"] == 0.15
    assert res["lueckenloses_rang_praefix"] is True


def test_ueber_das_feld_gestreute_sterne_sind_ein_statusabzeichen():
    # Gleich viele Sterne, aber quer durchs Feld -- kein Kranz-Muster.
    res = bewerte_sterne(_feld(100, {1, 9, 23, 40, 41, 55, 62, 70, 71, 80, 88, 90, 93, 97, 99}))
    assert res["befund"] == "statusabzeichen"
    assert res["lueckenloses_rang_praefix"] is False


def test_fast_alle_mit_stern_ist_ebenfalls_statusabzeichen():
    res = bewerte_sterne(_feld(100, set(range(1, 61))))
    assert res["befund"] == "statusabzeichen"


def test_kein_stern_wird_als_solcher_gemeldet():
    res = bewerte_sterne(_feld(100, set()))
    assert res["befund"] == "kein_stern_erkannt"
    assert res["n_stern"] == 0


def test_ohne_raenge_kein_urteil():
    assert bewerte_sterne([{"name": "X", "kranz": True}])["befund"] == "keine_raenge"


def test_rang_mit_buchstabensuffix_wird_gelesen():
    # Geteilte Raenge stehen als "3a"/"3b" in der Rangliste.
    feld = [{"rang": "3a", "name": "A", "kranz": True},
            {"rang": "3b", "name": "B", "kranz": True},
            {"rang": "4", "name": "C", "kranz": False}]
    res = bewerte_sterne(feld)
    assert res["n"] == 3 and res["n_stern"] == 2
