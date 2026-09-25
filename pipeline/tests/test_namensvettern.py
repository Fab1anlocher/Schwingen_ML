"""Namensvettern trennen: Klub eines anderen Teilverbands zur selben Zeit,
Jahrgang-Zusatz der Rangliste -- und was ausdrücklich NICHT getrennt wird."""
from __future__ import annotations

from pipeline.identity import baue_namensindex, namens_tokens
from pipeline.namensvettern import trenne_namensvettern
from pipeline.ranglisten import teilnahmen_aus_ranglisten
from pipeline.schema import Event, Schwinger

_P = ["schlussgang.ch/portraet"]


def _sw():
    s = {"giger": Schwinger(id="giger", name="Samuel Giger", jahrgang=1998, teilverband="Nordostschweiz", quellen=_P)}
    # Je drei Porträt-Mitglieder machen einen Klub eindeutig.
    for i in range(3):
        s[f"t{i}"] = Schwinger(id=f"t{i}", name=f"Thurgau Mitglied{i}", teilverband="Nordostschweiz", quellen=_P)
        s[f"l{i}"] = Schwinger(id=f"l{i}", name=f"Luzern Mitglied{i}", teilverband="Innerschweiz", quellen=_P)
    return s


def _rl(eintraege_je_fest: dict) -> dict:
    """Rangliste je Fest; die Klub-Mitglieder stehen an jedem Fest mit drin."""
    out = {}
    for eid, eintraege in eintraege_je_fest.items():
        mitglieder = [{"name": f"Mitglied{i} Thurgau", "schwingklub": "Ottoberg"} for i in range(3)]
        mitglieder += [{"name": f"Mitglied{i} Luzern", "schwingklub": "Wolhusen"} for i in range(3)]
        out[eid] = {"eintraege": eintraege + mitglieder}
    return out


def _events(*daten):
    return {f"e{i}": Event(id=f"e{i}", name=f"Fest {i}", datum=d, typ="regional", quelle="x")
            for i, d in enumerate(daten)}


def _laufe(rl, events, sw):
    idx = baue_namensindex([{"id": k, "name": v.name} for k, v in sw.items()])
    return trenne_namensvettern(rl, events, idx.finde, sw)


def _abwechselnd(n):
    """n Feste, abwechselnd für Ottoberg (Thurgau) und Wolhusen (Luzern)."""
    ev = _events(*[f"2024-{4 + i // 4:02d}-{1 + 7 * (i % 4):02d}" for i in range(n)])
    rl = _rl({f"e{i}": [{"name": "Giger Samuel", "schwingklub": "Ottoberg" if i % 2 == 0 else "Wolhusen"}]
              for i in range(n)})
    return ev, rl


def test_durchmischte_auftritte_sind_zwei_personen():
    ev, rl = _abwechselnd(8)  # 7 Wechsel
    zuordnung, neue, bericht = _laufe(rl, ev, _sw())
    t = namens_tokens("Samuel Giger")
    assert zuordnung == {(f"e{i}", t): "giger samuel|is" for i in (1, 3, 5, 7)}
    assert neue["giger samuel|is"]["namensvetter_von"] == "giger"
    assert bericht["personen_getrennt"] == 1 and bericht["feste_umgehaengt"] == 4


def test_fest_am_selben_tag_reicht_als_beleg():
    ev = _events("2024-05-01", "2024-05-01", "2024-06-01", "2024-07-01")
    rl = _rl({"e0": [{"name": "Giger Samuel", "schwingklub": "Ottoberg"}],
              "e1": [{"name": "Giger Samuel", "schwingklub": "Wolhusen"}],
              "e2": [{"name": "Giger Samuel", "schwingklub": "Ottoberg"}],
              "e3": [{"name": "Giger Samuel", "schwingklub": "Wolhusen"}]})
    zuordnung, _, _ = _laufe(rl, ev, _sw())
    assert set(zuordnung.values()) == {"giger samuel|is"} and len(zuordnung) == 2


def test_wenige_wechsel_ohne_selben_tag_bleiben_eine_person():
    """Hin und zurück (Théo Rogivue: 2024 Berner Klub, 2025 wieder Freiburger)."""
    ev = _events("2023-05-01", "2023-06-01", "2024-05-01", "2024-06-01", "2025-05-01", "2025-06-01")
    rl = _rl({f"e{i}": [{"name": "Giger Samuel", "schwingklub": k}]
              for i, k in enumerate(["Ottoberg", "Ottoberg", "Wolhusen", "Wolhusen", "Ottoberg", "Ottoberg"])})
    assert _laufe(rl, ev, _sw())[0] == {}


def test_klubwechsel_nacheinander_bleibt_eine_person():
    ev = _events("2023-05-01", "2023-06-01", "2025-05-01", "2025-06-01")
    rl = _rl({"e0": [{"name": "Giger Samuel", "schwingklub": "Wolhusen"}],
              "e1": [{"name": "Giger Samuel", "schwingklub": "Wolhusen"}],
              "e2": [{"name": "Giger Samuel", "schwingklub": "Ottoberg"}],
              "e3": [{"name": "Giger Samuel", "schwingklub": "Ottoberg"}]})
    zuordnung, neue, _ = _laufe(rl, ev, _sw())
    assert zuordnung == {} and neue == {}


def test_ein_einzelnes_fremdes_fest_reicht_nicht():
    ev = _events("2024-05-01", "2024-06-01", "2024-07-01")
    rl = _rl({"e0": [{"name": "Giger Samuel", "schwingklub": "Ottoberg"}],
              "e1": [{"name": "Giger Samuel", "schwingklub": "Wolhusen"}],
              "e2": [{"name": "Giger Samuel", "schwingklub": "Ottoberg"}]})
    assert _laufe(rl, ev, _sw())[0] == {}


def test_jahrgang_zusatz_trennt_sicher():
    ev = _events("2024-05-01")
    rl = _rl({"e0": [{"name": "Giger Samuel (2004)", "schwingklub": "Ottoberg"}]})
    zuordnung, neue, _ = _laufe(rl, ev, _sw())
    assert zuordnung == {("e0", namens_tokens("Samuel Giger")): "giger samuel|2004"}
    assert neue["giger samuel|2004"]["jahrgang"] == 2004


def test_beide_am_selben_fest_bleibt_wie_es_ist():
    ev = _events("2024-05-01")
    rl = _rl({"e0": [{"name": "Giger Samuel", "schwingklub": "Ottoberg"},
                     {"name": "Giger Samuel (2004)", "schwingklub": "Wolhusen"}]})
    zuordnung, _, bericht = _laufe(rl, ev, _sw())
    assert zuordnung == {} and bericht["nicht_trennbar_selbes_fest"] == 1


def test_teilnahmen_folgen_der_zuordnung():
    ev, rl = _abwechselnd(8)
    sw = _sw()
    zuordnung, neue, _ = _laufe(rl, ev, sw)
    idx = baue_namensindex([{"id": k, "name": v.name} for k, v in sw.items()])
    teilnahmen, _ = teilnahmen_aus_ranglisten(rl, ev, idx.finde, sw, zuordnung=zuordnung)
    giger = sorted((t.event_id, t.schwinger_id) for t in teilnahmen if "giger" in t.schwinger_id)
    assert giger == [(f"e{i}", "giger" if i % 2 == 0 else "giger samuel|is") for i in range(8)]
