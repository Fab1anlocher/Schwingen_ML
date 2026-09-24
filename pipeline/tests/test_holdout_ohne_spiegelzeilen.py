"""Der Holdout darf keine augmentierten Spiegelzeilen enthalten, und die
Elo-Baseline muss auf derselben Gang-Menge gemessen werden wie das Modell."""
from __future__ import annotations

from pipeline.labels import GangResultat
from pipeline.ratings import bewerte_baseline
from pipeline.train import _split_zeitlich, holdout_gang_schluessel


def _meta(event, a, b, datum, augmented=False):
    m = {"event_id": event, "datum": datum, "schwinger_a_id": a, "schwinger_b_id": b}
    if augmented:
        m["augmented"] = True
    return m


def _paar(event, a, b, datum):
    """Ein echter Gang + seine Spiegelzeile, wie baue_features sie erzeugt."""
    return [_meta(event, a, b, datum), _meta(event, a, b, datum, augmented=True)]


def test_spiegelzeilen_bleiben_im_training_aber_nicht_im_test():
    meta = _paar("ev_alt", "a|1", "b|2", "2024-05-01") + _paar("ev_neu", "c|3", "d|4", "2026-05-01")
    X = [[float(i)] for i in range(len(meta))]
    y = [0, 2, 0, 2]
    Xtr, ytr, Xte, yte = _split_zeitlich(X, y, meta, holdout_ab_jahr=2026)

    assert len(Xtr) == 2, "Training behaelt die Spiegelzeile (Paar-Symmetrie)"
    assert len(Xte) == 1, "Test enthaelt jeden Gang genau einmal"


def test_ohne_den_filter_waere_der_test_doppelt_so_gross():
    """Gegenprobe: genau das war der Fehler -- n_test 72'970 statt 36'485."""
    meta = _paar("ev", "a|1", "b|2", "2026-05-01")
    X, y = [[0.0], [1.0]], [0, 2]
    _, _, Xte, _ = _split_zeitlich(X, y, meta, holdout_ab_jahr=2026)
    assert len(Xte) == 1
    assert len(Xte) * 2 == len(meta)


def test_holdout_schluessel_liefert_nur_echte_holdout_gaenge():
    meta = _paar("ev_alt", "a|1", "b|2", "2024-05-01") + _paar("ev_neu", "c|3", "d|4", "2026-05-01")
    assert holdout_gang_schluessel(meta, 2026) == {("ev_neu", "c|3", "d|4")}


def _gang(event, a, b, datum, ergebnis="sieg_a"):
    return GangResultat(
        event_id=event, datum=datum, schwinger_a_id=a, schwinger_b_id=b,
        symbol_a="+", note_a=10.0, symbol_b="o", note_b=8.5,
        ergebnis=ergebnis, fest_typ="kantonal",
    )


def _snap(event, a, b, elo_a=1600.0, elo_b=1500.0):
    return {"event_id": event, "schwinger_a_id": a, "schwinger_b_id": b,
            "elo_a_pre": elo_a, "elo_b_pre": elo_b, "n_a_pre": 10, "n_b_pre": 10}


def test_baseline_ohne_einschraenkung_nimmt_alle_jahre():
    """Der alte Zustand: die Baseline sah auch die Trainingsjahre."""
    gaenge = [_gang("ev_alt", "a|1", "b|2", "2024-05-01"),
              _gang("ev_neu", "c|3", "d|4", "2026-05-01")]
    snaps = [_snap("ev_alt", "a|1", "b|2"), _snap("ev_neu", "c|3", "d|4")]
    assert bewerte_baseline(gaenge, snaps, ["sieg_a", "gestellt", "sieg_b"])["n"] == 2


def test_baseline_auf_dem_holdout_des_modells():
    """Neu: exakt die Gänge, auf denen auch das Modell bewertet wird."""
    gaenge = [_gang("ev_alt", "a|1", "b|2", "2024-05-01"),
              _gang("ev_neu", "c|3", "d|4", "2026-05-01")]
    snaps = [_snap("ev_alt", "a|1", "b|2"), _snap("ev_neu", "c|3", "d|4")]
    meta = _paar("ev_alt", "a|1", "b|2", "2024-05-01") + _paar("ev_neu", "c|3", "d|4", "2026-05-01")
    res = bewerte_baseline(gaenge, snaps, ["sieg_a", "gestellt", "sieg_b"],
                           nur_gaenge=holdout_gang_schluessel(meta, 2026))
    assert res["n"] == 1, "nur der Holdout-Gang zaehlt"
