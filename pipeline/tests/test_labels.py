"""Tests für die kritische Label-Ableitung, Dedup und Validierung (§4.3)."""
from __future__ import annotations

import pytest

from pipeline.labels import (
    ergebnis_aus_symbolen,
    dedupliziere,
    validiere_punktetotal,
    RohGangEintrag,
    LabelError,
)


def test_symbol_sieg():
    assert ergebnis_aus_symbolen("+", "o") == "sieg_a"


def test_symbol_niederlage():
    assert ergebnis_aus_symbolen("o", "+") == "sieg_b"


def test_symbol_gestellt():
    assert ergebnis_aus_symbolen("-", "-") == "gestellt"


def test_inkonsistente_symbole_fehler():
    # + muss o gegenüberstehen, nicht -
    with pytest.raises(LabelError):
        ergebnis_aus_symbolen("+", "-")
    with pytest.raises(LabelError):
        ergebnis_aus_symbolen("+", "+")


def test_unbekanntes_symbol():
    with pytest.raises(LabelError):
        ergebnis_aus_symbolen("x", "o")


def test_dedup_zwei_perspektiven_ergibt_einen_gang():
    # Zwei PDF-Perspektiven desselben Gangs -> genau ein deduplizierter Gang.
    roh = [
        RohGangEintrag("ev1", "2024-05-01", "anna|1995", "beat|1996", "+", 10.0, "kantonal"),
        RohGangEintrag("ev1", "2024-05-01", "beat|1996", "anna|1995", "o", 8.75, "kantonal"),
    ]
    gaenge, warnungen = dedupliziere(roh)
    assert len(gaenge) == 1
    assert warnungen == []
    g = gaenge[0]
    # Kanonische A-Seite = lexikographisch kleinere ID ("anna|1995").
    assert g.schwinger_a_id == "anna|1995"
    assert g.ergebnis == "sieg_a"


def test_dedup_gestellt():
    roh = [
        RohGangEintrag("ev1", "2024-05-01", "anna|1995", "beat|1996", "-", 8.75, "berg"),
        RohGangEintrag("ev1", "2024-05-01", "beat|1996", "anna|1995", "-", 9.00, "berg"),
    ]
    gaenge, warnungen = dedupliziere(roh)
    assert len(gaenge) == 1
    assert gaenge[0].ergebnis == "gestellt"


def test_dedup_inkonsistenz_wird_verworfen():
    roh = [
        RohGangEintrag("ev1", "2024-05-01", "anna|1995", "beat|1996", "+", 10.0, "kantonal"),
        RohGangEintrag("ev1", "2024-05-01", "beat|1996", "anna|1995", "-", 9.00, "kantonal"),
    ]
    gaenge, warnungen = dedupliziere(roh)
    assert len(gaenge) == 0
    assert len(warnungen) == 1


def test_dedup_einzelne_perspektive_warnt():
    roh = [
        RohGangEintrag("ev1", "2024-05-01", "anna|1995", "beat|1996", "+", 10.0, "regional"),
    ]
    gaenge, warnungen = dedupliziere(roh)
    assert len(gaenge) == 1
    assert any("nur eine Perspektive" in w for w in warnungen)


def test_punktetotal_ok():
    assert validiere_punktetotal("anna|1995", [10.0, 9.75, 8.75], 28.50) is None


def test_punktetotal_abweichung():
    fehler = validiere_punktetotal("anna|1995", [10.0, 9.75], 28.50)
    assert fehler is not None and "Abweichung" in fehler
