"""P3 / Merkmalsversion 2: Stand vor dem Fest, Elo in Einheiten der Streuung,
Erfahrung logarithmisch, Gestellt-Neigung, Einschwingphase und die
Versionsweiche für ältere ausgelieferte Modelle."""
from __future__ import annotations

import math

import numpy as np

from pipeline.config import ELO_STREUUNG_ERSATZ, ELO_STREUUNG_UNTERGRENZE, GESTELLT_NEIGUNG_K
from pipeline.features import (
    FEATURE_NAMES,
    baue_features,
    feature_vektor_fuer_prognose,
    gestellt_neigung_aktuell,
    paar_neigung,
)
from pipeline.labels import GangResultat
from pipeline.metriken import gestellt_kalibrierung
from pipeline.ratings import EloModell, elo_streuung, fahre_elo_durch
from pipeline.schema import Schwinger
from pipeline.train import trainings_maske

_I = {n: i for i, n in enumerate(FEATURE_NAMES)}
_SYMBOLE = {"sieg_a": ("+", "o"), "gestellt": ("-", "-"), "sieg_b": ("o", "+")}


def _gang(event, datum, a, b, ergebnis="sieg_a"):
    sa, sb = _SYMBOLE[ergebnis]
    return GangResultat(
        event_id=event, datum=datum, schwinger_a_id=a, schwinger_b_id=b,
        symbol_a=sa, note_a=None, symbol_b=sb, note_b=None,
        ergebnis=ergebnis, fest_typ="kantonal",
    )


def _sw(*ids):
    return {i: Schwinger(id=i, name=i) for i in ids}


def _zeilen(gaenge, schwinger):
    _, snaps = fahre_elo_durch(gaenge)
    X, y, meta = baue_features(gaenge, snaps, schwinger, augment=True)
    return X, y, meta


# --- Stand vor dem Fest ----------------------------------------------------------

def test_alle_gaenge_eines_fests_sehen_den_stand_vor_dem_fest():
    """Zweiter Gang desselben Fests: weder Elo noch Form noch Kopf-an-Kopf
    dürfen den ersten Gang schon enthalten -- die Verarbeitungsreihenfolge
    innerhalb eines Fests folgt dem Schlussrang, nicht der Gangfolge."""
    gaenge = [_gang("f1", "2024-05-01", "a", "b"), _gang("f1", "2024-05-01", "a", "c")]
    X, _, meta = _zeilen(gaenge, _sw("a", "b", "c"))
    zweiter = next(x for x, m in zip(X, meta) if m["schwinger_b_id"] == "c" and not m.get("augmented"))
    assert zweiter[_I["rating_diff"]] == 0.0      # a noch auf Startwert
    assert zweiter[_I["form_diff"]] == 0.0         # Sieg gegen b noch nicht in der Form
    assert zweiter[_I["erfahrung_diff"]] == 0.0    # a hat vor dem Fest 0 Gänge


def test_nach_dem_fest_fliesst_alles_ein():
    gaenge = [_gang("f1", "2024-05-01", "a", "b"), _gang("f2", "2024-06-01", "a", "b")]
    X, _, meta = _zeilen(gaenge, _sw("a", "b"))
    x2 = next(x for x, m in zip(X, meta) if m["event_id"] == "f2" and not m.get("augmented"))
    assert x2[_I["rating_diff"]] > 0 and x2[_I["form_diff"]] > 0 and x2[_I["kopf_an_kopf"]] > 0


def test_endstand_der_ratings_bleibt_derselbe():
    """Eingefroren werden nur die MERKMALE; die Fortschreibung ist unverändert."""
    gaenge = [_gang("f1", "2024-05-01", "a", "b"), _gang("f1", "2024-05-01", "a", "c", "gestellt"),
              _gang("f2", "2024-06-01", "b", "c", "sieg_b")]
    modell, _ = fahre_elo_durch(gaenge)
    einzeln = EloModell()
    for g in sorted(gaenge, key=lambda g: (g.datum, g.event_id)):
        einzeln.update(g)
    assert modell.ratings == einzeln.ratings


def test_meta_traegt_den_rohen_elo_abstand():
    gaenge = [_gang("f1", "2024-05-01", "a", "b"), _gang("f2", "2024-06-01", "a", "b")]
    _, _, meta = _zeilen(gaenge, _sw("a", "b"))
    m2 = [m for m in meta if m["event_id"] == "f2"]
    assert m2[0]["elo_diff"] > 0 and math.isclose(m2[1]["elo_diff"], -m2[0]["elo_diff"])


# --- Streuung --------------------------------------------------------------------

def _modell_mit(ratings: dict[str, float], tag: str) -> EloModell:
    m = EloModell()
    m.ratings = dict(ratings)
    m.letzter_gang = {sid: tag for sid in ratings}
    return m


def test_streuung_ist_die_standardabweichung_der_aktiven():
    werte = {f"s{i}": 1500.0 + (40 if i % 2 else -40) for i in range(40)}
    assert math.isclose(elo_streuung(_modell_mit(werte, "2025-06-01"), "2025-07-01"), 40.0)


def test_inaktive_zaehlen_nicht():
    """Wer über ein Jahr keinen Gang hatte, behält ein eingefrorenes Rating --
    das würde die Streuung der heute Antretenden verfälschen."""
    aktiv = _modell_mit({f"s{i}": 1500.0 + (40 if i % 2 else -40) for i in range(40)}, "2025-06-01")
    aktiv.ratings |= {"alt1": 2500.0, "alt2": 500.0}
    aktiv.letzter_gang |= {"alt1": "2023-01-01", "alt2": "2023-01-01"}
    assert math.isclose(elo_streuung(aktiv, "2025-07-01"), 40.0)


def test_streuung_ersatz_und_untergrenze():
    wenige = _modell_mit({f"s{i}": 1500.0 + i for i in range(5)}, "2025-06-01")
    assert elo_streuung(wenige, "2025-07-01") == ELO_STREUUNG_ERSATZ
    gleich = _modell_mit({f"s{i}": 1500.0 for i in range(40)}, "2025-06-01")
    assert elo_streuung(gleich, "2025-07-01") == ELO_STREUUNG_UNTERGRENZE


# --- Gestellt-Neigung --------------------------------------------------------------

def test_neigung_ist_leakfrei_und_im_ersten_fest_null():
    gaenge = [_gang("f1", "2024-05-01", "a", "b", "gestellt")]
    X, _, _ = _zeilen(gaenge, _sw("a", "b"))
    assert all(x[_I["gestellt_neigung"]] == 0.0 for x in X)


def test_neigung_ist_symmetrisch_in_beiden_zeilen():
    gaenge = [_gang("f1", "2024-05-01", "a", "b", "gestellt"), _gang("f1", "2024-05-01", "c", "d"),
              _gang("f2", "2024-06-01", "a", "c")]
    X, _, meta = _zeilen(gaenge, _sw("a", "b", "c", "d"))
    f2 = [x for x, m in zip(X, meta) if m["event_id"] == "f2"]
    assert f2[0][_I["gestellt_neigung"]] == f2[1][_I["gestellt_neigung"]]
    # Basis vor f2: 1 von 2 Gängen gestellt. a: 1/1 gestellt, c: 0/1.
    basis = 0.5
    n_a = (1 + GESTELLT_NEIGUNG_K * basis) / (1 + GESTELLT_NEIGUNG_K)
    n_c = (0 + GESTELLT_NEIGUNG_K * basis) / (1 + GESTELLT_NEIGUNG_K)
    assert math.isclose(f2[0][_I["gestellt_neigung"]], (n_a + n_c) / 2 - basis)


def test_export_wert_entspricht_dem_trainingsmerkmal_beim_naechsten_fest():
    """Die App rechnet mit dem exportierten Stand; das Training sah beim
    nächsten Fest genau diesen Stand. Beide müssen dieselbe Grösse sein."""
    vorher = [_gang("f1", "2024-05-01", "a", "b", "gestellt"), _gang("f1", "2024-05-01", "c", "d"),
              _gang("f2", "2024-06-01", "a", "c", "gestellt"), _gang("f2", "2024-06-01", "b", "d", "sieg_b")]
    sw = _sw("a", "b", "c", "d")
    neigung, basis = gestellt_neigung_aktuell(vorher, sw)
    X, _, meta = _zeilen(vorher + [_gang("f3", "2024-07-01", "a", "d")], sw)
    x3 = next(x for x, m in zip(X, meta) if m["event_id"] == "f3")
    assert math.isclose(x3[_I["gestellt_neigung"]], paar_neigung(neigung["a"], neigung["d"], basis))


# --- Versionsweiche ----------------------------------------------------------------

_V2 = {"merkmal_version": 2, "elo_streuung": 125.0, "gestellt_basis": 0.2}


def _live(cfg, **kw):
    sa, sb = Schwinger(id="a", name="a"), Schwinger(id="b", name="b")
    return feature_vektor_fuer_prognose(1750, 1500, 0.6, 0.4, 100, 9, sa, sb, "2026-06-01", 0.0,
                                        modell_config=cfg, **kw)


def test_modell_ohne_versionsangabe_rechnet_nach_version_1():
    x = _live({"kranzstatus_ordinal": {}})
    assert len(x) == 13
    assert x[_I["rating_diff"]] == 2.5 and x[_I["erfahrung_diff"]] == 91.0


def test_version_2_skaliert_mit_der_streuung_und_logarithmiert():
    x = _live(_V2, neigung_a=0.3, neigung_b=0.2)
    assert len(x) == len(FEATURE_NAMES)
    assert x[_I["rating_diff"]] == 250 / 125.0
    assert math.isclose(x[_I["erfahrung_diff"]], math.log1p(100) - math.log1p(9))
    assert math.isclose(x[_I["gestellt_neigung"]], 0.05)


def test_fehlende_neigung_gilt_als_durchschnitt():
    assert _live(_V2)[_I["gestellt_neigung"]] == 0.0
    assert math.isclose(_live(_V2, neigung_a=0.4)[_I["gestellt_neigung"]], 0.1)


# --- Einschwingphase ---------------------------------------------------------------

def _meta(datum):
    return {"datum": datum}


def test_erstes_jahr_liefert_nur_historie():
    meta = [_meta("2023-05-01"), _meta("2023-09-01"), _meta("2024-05-02"), _meta("2024-06-01"),
            _meta("2025-05-01")]
    y = [0, 1, 0, 2, 1]
    maske = trainings_maske(meta, y, holdout_ab_jahr=2025)
    assert maske.tolist() == [False, False, True, True, False]


def test_ohne_brauchbares_training_gilt_die_maske_ohne_einschwingphase():
    """Kurze Datenbasis (z.B. synthetische Daten): lieber mit Einschwingphase
    trainieren als gar nicht."""
    meta = [_meta("2024-05-01"), _meta("2024-06-01"), _meta("2025-05-01")]
    maske = trainings_maske(meta, [0, 2, 1], holdout_ab_jahr=2025)
    assert maske.tolist() == [True, True, False]


# --- Kalibrierung ------------------------------------------------------------------

def test_kalibrierung_erkennt_systematisch_zu_tiefes_gestellt():
    rng = np.random.default_rng(0)
    n = 4000
    y = rng.choice(3, size=n, p=[0.4, 0.2, 0.4])
    gut = np.tile([0.4, 0.2, 0.4], (n, 1))
    zu_tief = np.tile([0.45, 0.1, 0.45], (n, 1))
    assert gestellt_kalibrierung(gut, y)["ece"] < 0.03
    k = gestellt_kalibrierung(zu_tief, y)
    assert k["vorhergesagt"] == 0.1 and k["ece"] > 0.08
    assert sum(s["n"] for s in k["stufen"]) == n
