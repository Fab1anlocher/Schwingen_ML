"""Python-Seite der TS/Python-Paritätsprüfung (pipeline/paritaet.py).

Die eigentliche Gegenüberstellung mit TypeScript läuft im CI-Job
`inferenz-paritaet` (Node). Hier wird geprüft, dass die Python-Referenz
selbst stimmt -- eine falsche Referenz machte den ganzen Vergleich wertlos.
Bewusst mit kleinen, selbst gebauten Artefakten statt der committeten,
damit der Test nicht vom Datenstand abhängt.
"""
from __future__ import annotations

import json
import math

from pipeline.features import FEATURE_NAMES, MERKMALE_JE_VERSION, paar_gestellt
from pipeline.paritaet import _h2h_python, erzeuge_faelle, json_inferenz_wie_app


def _modell(n: int, *, version: int = 1) -> dict:
    config = {"kranzstatus_ordinal": {"kein": 0, "kranzer": 1, "eidgenosse": 2, "koenig": 3}}
    if version >= 2:
        config |= {"merkmal_version": version, "elo_streuung": 120.0, "gestellt_basis": 0.22}
    return {
        "features": [f"m{i}" for i in range(n)],
        "klassen": ["sieg_a", "gestellt", "sieg_b"],
        "standardisierung": {"mu": [0.0] * n, "sigma": [1.0] * n},
        "coef": [[0.1 * (i + 1) for i in range(n)], [0.0] * n, [-0.1 * (i + 1) for i in range(n)]],
        "intercept": [0.0, -0.5, 0.0],
        "config": config,
    }


def test_inferenz_kuerzt_auf_die_merkmale_des_modells():
    """Wie die App: ein Modell, das dem Code hinterherhinkt, sieht nur die ersten N."""
    m = _modell(2)
    p_kurz = json_inferenz_wie_app(m, [1.0, 2.0])
    p_lang = json_inferenz_wie_app(m, [1.0, 2.0, 999.0])
    assert p_kurz == p_lang
    assert math.isclose(sum(p_kurz), 1.0)


def test_inferenz_sigma_null_wird_wie_in_der_app_zu_eins():
    m = _modell(1)
    m["standardisierung"]["sigma"] = [0.0]
    assert all(math.isfinite(v) for v in json_inferenz_wie_app(m, [3.0]))


def test_kopf_an_kopf_ist_antisymmetrisch():
    """Die API liefert aus Sicht der kleineren ID -- A>B muss das Vorzeichen drehen."""
    treffer = [{"event_id": "e1", "ergebnis": "sieg_a"}, {"event_id": "e2", "ergebnis": "sieg_a"}]
    assert _h2h_python("a|1", "b|2", treffer) > 0
    assert math.isclose(_h2h_python("a|1", "b|2", treffer), -_h2h_python("b|2", "a|1", treffer))
    assert _h2h_python("a|1", "b|2", []) == 0.0


def _artefakte(tmp_path):
    por = lambda i, **kw: {"id": f"p{i}|1990", "name": f"P{i}", "jahrgang": 1990 + i, "gewicht_kg": 100.0 + i,
                           "groesse_cm": 180.0, "kranzstatus": "kranzer", "teilverband": "Bern",
                           "bevorzugte_schwuenge": ["Kurz"], "form": 0.6, "gestellt_neigung": 0.2 + 0.02 * i,
                           "quellen": ["schlussgang.ch/portraet", "https://www.schlussgang.ch/portraet/x"], **kw}
    stub = lambda i: {"id": f"s{i}|?", "name": f"S{i}", "jahrgang": None, "gewicht_kg": None, "groesse_cm": None,
                      "kranzstatus": "kein", "teilverband": None, "bevorzugte_schwuenge": [], "form": 0.4,
                      "quellen": ["schlussgang.ch/statistic-pdf"]}
    sw = [por(i) for i in range(4)] + [stub(i) for i in range(4)]
    ids = [s["id"] for s in sw]
    (tmp_path / "schwinger.json").write_text(json.dumps({"schwinger": sw}))
    (tmp_path / "ratings.json").write_text(json.dumps(
        {"elo_start": 1500, "ratings": {sid: {"elo": 1500 + 10 * i, "n_gaenge": 5 * i} for i, sid in enumerate(ids)}}))
    (tmp_path / "kopf_an_kopf.json").write_text(json.dumps({
        "index": {sid: i for i, sid in enumerate(ids)}, "event_index": {"e1": 0, "e2": 1},
        "paare": {"0_4": [[0, "A"], [1, "D"]], "1_5": [[0, "B"], [1, "B"]]},
    }))
    (tmp_path / "model.json").write_text(json.dumps(_modell(len(FEATURE_NAMES), version=3)))
    return tmp_path


def test_faelle_decken_alle_datenlagen_und_beide_richtungen_ab(tmp_path):
    daten = erzeuge_faelle(_artefakte(tmp_path), n_je_gruppe=5)
    gruppen = {f["gruppe"] for f in daten["faelle"]}
    assert {"portraet-portraet", "portraet-stub", "stub-portraet", "stub-stub",
            "historie-a<b", "historie-a>b", "ohne-rating", "ohne-neigung",
            "modell-v1", "modell-v2"} <= gruppen
    for f in daten["faelle"]:
        n = MERKMALE_JE_VERSION[int(f.get("modell", "v3")[1:])]
        assert len(f["erwartet"]["merkmale"]) == n
        assert math.isclose(sum(f["erwartet"]["wahrscheinlichkeiten"]), 1.0)


def test_aeltere_gestalten_haben_ihre_merkmalszahl_und_versionsangabe(tmp_path):
    daten = erzeuge_faelle(_artefakte(tmp_path), n_je_gruppe=2)
    v1, v2 = daten["modelle_alt"]["v1"], daten["modelle_alt"]["v2"]
    assert len(v1["features"]) == 13 and all(len(z) == 13 for z in v1["coef"])
    assert "merkmal_version" not in v1["config"] and "elo_streuung" not in v1["config"]
    assert len(v2["features"]) == 14 and all(len(z) == 14 for z in v2["coef"])
    assert v2["config"]["merkmal_version"] == 2 and v2["config"]["gestellt_basis"] == 0.22


def test_paar_bilanz_kommt_aus_der_api_historie(tmp_path):
    """p0 gegen s0: ein Sieg, ein Gestellt -> 2 Duelle, 1 gestellt; ohne Historie 0."""
    daten = erzeuge_faelle(_artefakte(tmp_path), n_je_gruppe=40)
    i = FEATURE_NAMES.index("paar_gestellt")
    for f in daten["faelle"]:
        if f.get("modell"):
            continue
        e = f["erwartet"]
        assert e["duelle"] == len(f["treffer_kanonisch"])
        na = f["a"].get("gestellt_neigung")
        nb = f["b"].get("gestellt_neigung")
        na, nb = (0.22 if na is None else na), (0.22 if nb is None else nb)
        assert math.isclose(e["merkmale"][i], paar_gestellt(e["duelle"], e["duelle_gestellt"], na, nb),
                            abs_tol=1e-12)
    paar = next(f for f in daten["faelle"] if {f["a"]["id"], f["b"]["id"]} == {"p0|1990", "s0|?"})
    assert (paar["erwartet"]["duelle"], paar["erwartet"]["duelle_gestellt"]) == (2, 1)


def test_fehlende_neigung_zaehlt_als_durchschnitt(tmp_path):
    """Fehlender Eintrag bzw. null -> Basis 0.22; es zählt nur noch der Partner."""
    daten = erzeuge_faelle(_artefakte(tmp_path), n_je_gruppe=8)
    faelle = [f for f in daten["faelle"] if f["gruppe"] == "ohne-neigung"]
    assert any("gestellt_neigung" not in f["a"] for f in faelle)
    assert any(f["b"].get("gestellt_neigung", 0) is None for f in faelle)
    for f in faelle:
        na = f["a"].get("gestellt_neigung")
        nb = f["b"].get("gestellt_neigung")
        erwartet = ((0.22 if na is None else na) + (0.22 if nb is None else nb)) / 2 - 0.22
        i = FEATURE_NAMES.index("gestellt_neigung")
        assert math.isclose(f["erwartet"]["merkmale"][i], erwartet, abs_tol=1e-12)


def test_fall_ohne_rating_nutzt_den_fallback_der_app(tmp_path):
    daten = erzeuge_faelle(_artefakte(tmp_path), n_je_gruppe=2)
    f = next(f for f in daten["faelle"] if f["gruppe"] == "ohne-rating")
    assert f["rating_a"] == {"elo": 1500, "n_gaenge": 0}
