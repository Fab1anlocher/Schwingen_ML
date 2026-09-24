"""P2: Die Datenlage (Porträt ja/nein) ist ein offenes Merkmal statt ein
verdecktes, und die Modellgüte wird zusätzlich nur auf Porträt-gegen-Porträt-
Gängen gemessen."""
from __future__ import annotations

import numpy as np

from pipeline.features import FEATURE_NAMES, feature_vektor_fuer_prognose
from pipeline.schema import Schwinger, hat_portraet
from pipeline.train import _bewerte_nur_portraet, holdout_gang_schluessel

_IDX = FEATURE_NAMES.index("portraet_diff")
_PORTRAET = ["schlussgang.ch/portraet", "https://www.schlussgang.ch/portraet/x"]
_STUB = ["schlussgang.ch/statistic-pdf"]


def _s(sid, quellen, kranzstatus="kein", **kw):
    return Schwinger(id=sid, name=sid, quellen=quellen, kranzstatus=kranzstatus, **kw)


def _vektor(sa, sb):
    return feature_vektor_fuer_prognose(1600, 1500, 0.5, 0.5, 10, 10, sa, sb, "2026-06-01", 0.0)


# --- Erkennung -----------------------------------------------------------------

def test_portraet_wird_ueber_die_quelle_erkannt():
    assert hat_portraet(_PORTRAET) is True
    assert hat_portraet(_STUB) is False
    assert hat_portraet([]) is False
    assert hat_portraet(None) is False


def test_portraet_erkennung_ist_nicht_der_kranzstatus():
    """Nicht zirkulär: schlussgang.ch porträtiert nur Kranzer und besser, ein
    Kranzstatus-Test würde also dieselbe Information zweimal verwenden. Ein
    Porträt ohne Kranzstatus wird trotzdem als Porträt erkannt."""
    assert hat_portraet(_s("x|1", _PORTRAET, kranzstatus="kein").quellen) is True


# --- Merkmal -----------------------------------------------------------------

def test_portraet_diff_ist_das_letzte_merkmal():
    """Positionsgebunden in model.json: neue Merkmale nur HINTEN anhängen,
    sonst verrutschen die Koeffizienten eines älteren ausgelieferten Modells."""
    assert FEATURE_NAMES[-1] == "portraet_diff"


def test_portraet_diff_werte_je_konstellation():
    por, stub = _s("p|1", _PORTRAET, "kranzer"), _s("s|2", _STUB)
    assert _vektor(por, stub)[_IDX] == 1.0
    assert _vektor(stub, por)[_IDX] == -1.0
    assert _vektor(por, _s("q|3", _PORTRAET, "kranzer"))[_IDX] == 0.0
    assert _vektor(stub, _s("t|4", _STUB))[_IDX] == 0.0


def test_portraet_diff_ist_antisymmetrisch():
    """Die Augmentation vertauscht A und B -- das Merkmal muss das Vorzeichen
    wechseln, sonst wäre das Modell nicht mehr paar-symmetrisch."""
    por, stub = _s("p|1", _PORTRAET, "kranzer"), _s("s|2", _STUB)
    assert _vektor(por, stub)[_IDX] == -_vektor(stub, por)[_IDX]


# --- Auswertung nur auf Porträt-Gängen -------------------------------------------

def _meta(event, datum, beide, augmented=False):
    m = {"event_id": event, "datum": datum, "schwinger_a_id": event + "a",
         "schwinger_b_id": event + "b", "beide_portraet": beide}
    if augmented:
        m["augmented"] = True
    return m


def test_holdout_schluessel_nur_porträt():
    meta = [
        _meta("e1", "2026-05-01", beide=True),
        _meta("e1", "2026-05-01", beide=True, augmented=True),
        _meta("e2", "2026-05-01", beide=False),
        _meta("e3", "2024-05-01", beide=True),  # Trainingsjahr
    ]
    alle = holdout_gang_schluessel(meta, 2026)
    nur = holdout_gang_schluessel(meta, 2026, nur_beide_portraet=True)
    assert alle == {("e1", "e1a", "e1b"), ("e2", "e2a", "e2b")}
    assert nur == {("e1", "e1a", "e1b")}


def test_bewerte_nur_portraet_rechnet_nur_auf_der_teilmenge():
    """Zwei Testgänge: der Porträt-Gang perfekt getroffen, der Stub-Gang völlig
    daneben. Die Teilauswertung darf nur den ersten sehen."""
    meta = [_meta("e1", "2026-05-01", beide=True),
            _meta("e2", "2026-05-01", beide=False)]
    p = np.array([[1.0, 0.0, 0.0],      # e1: sicher Sieg A
                  [1.0, 0.0, 0.0]])     # e2: sicher Sieg A
    y = np.array([0, 2])                # e1 richtig, e2 falsch
    res = _bewerte_nur_portraet(p, y, meta, 2026, [0, 1, 2])
    assert res["n"] == 1
    assert res["anteil_am_test"] == 0.5
    assert res["accuracy"] == 1.0
    assert res["mae"] == 0.0


def test_bewerte_nur_portraet_ohne_porträt_gänge():
    meta = [_meta("e1", "2026-05-01", beide=False)]
    res = _bewerte_nur_portraet(np.array([[1.0, 0, 0]]), np.array([0]), meta, 2026, [0, 1, 2])
    assert res == {"n": 0}
