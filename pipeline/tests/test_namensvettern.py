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


def test_mehrdeutiger_name_wird_je_fest_ueber_rangliste_aufgeloest():
    """Zwei Porträts "Roman Bucher": der Index lässt den Namen offen, die
    Rangliste entscheidet je Fest -- über den Jahrgang oder den Klub-Verband."""
    sw = _sw()
    sw["b02"] = Schwinger(id="b02", name="Roman Bucher", jahrgang=2002, teilverband="Innerschweiz", quellen=_P)
    sw["b03"] = Schwinger(id="b03", name="Roman Bucher", jahrgang=2003, teilverband="Nordostschweiz", quellen=_P)
    ev = _events("2024-05-01", "2024-06-01", "2024-07-01")
    rl = _rl({"e0": [{"name": "Bucher Roman (2003)", "schwingklub": "Wolhusen"}],
              "e1": [{"name": "Bucher Roman", "schwingklub": "Wolhusen"}],
              "e2": [{"name": "Bucher Roman", "schwingklub": "Unbekannt"}]})
    zuordnung, neue, bericht = _laufe(rl, ev, sw)
    t = namens_tokens("Roman Bucher")
    assert zuordnung == {("e0", t): "b03", ("e1", t): "b02"}  # e2: Klub ohne Verband -> offen
    assert neue == {} and bericht["mehrdeutige_feste_aufgeloest"] == 2


# --- Stufe 2: Herkunft (Klub, Wohnort) -- Roadmap D5 --------------------------

from pipeline.namensvettern import herkunft, herkunft_gruppen, klub_schluessel, trenne_nach_herkunft


def test_klub_in_der_wohnortspalte_wird_erkannt():
    bekannt = {"siehen", "lungern"}
    assert herkunft({"wohnort": "Süderen Siehen", "schwingklub": None}, bekannt) == "siehen"
    assert herkunft({"wohnort": "Lungern ONSVLungern"}, bekannt) == "lungern"
    assert herkunft({"wohnort": "Irgendwo"}, bekannt) is None
    assert klub_schluessel("SK am Mythen") == "ammythen"
    assert klub_schluessel("Mittel-Rheintal") == klub_schluessel("Mittelrheintal")


def test_selbes_fest_trennt_auch_bei_gleichem_wohnort():
    """Alex Schuler: zwei Personen aus Rothenthurm, oft am selben Fest."""
    auftritte = {"ammythen": [("2025-06-15", "a"), ("2025-07-06", "b"), ("2025-08-01", "c")],
                 "einsiedeln": [("2025-06-15", "a"), ("2025-07-06", "b")]}
    wohnorte = {"ammythen": {"rothenthurm"}, "einsiedeln": {"rothenthurm"}}
    assert herkunft_gruppen(auftritte, wohnorte) == [{"ammythen"}, {"einsiedeln"}]


def test_abwechselnde_schreibweisen_am_selben_wohnort_bleiben_eine_person():
    """Ständiges Abwechseln ohne Fest am selben Tag ist nur bei verschiedenen
    Wohnorten ein Beleg -- sonst kann es ein Klub mit zwei Schreibweisen sein."""
    tage = [f"2024-{4 + i // 4:02d}-{1 + 7 * (i % 4):02d}" for i in range(12)]
    auftritte = {"sensebezirk": [(t, f"f{i}") for i, t in enumerate(tage) if i % 2 == 0],
                 "sense": [(t, f"f{i}") for i, t in enumerate(tage) if i % 2 == 1]}
    assert herkunft_gruppen(auftritte, {"sensebezirk": {"tafers"}, "sense": {"tafers"}}) == [
        {"sensebezirk", "sense"}]
    assert len(herkunft_gruppen(auftritte, {"sensebezirk": {"tafers"}, "sense": {"plaffeien"}})) == 2


def test_klubwechsel_ohne_beleg_bleibt_eine_person():
    auftritte = {"surental": [(f"2024-0{m}-01", f"s{m}") for m in range(4, 9)],
                 "zofingen": [(f"2025-0{m}-01", f"z{m}") for m in range(4, 9)]}
    assert herkunft_gruppen(auftritte, {}) == [{"surental", "zofingen"}]


def test_gleicher_wohnort_bindet_und_belegter_konflikt_trennt():
    """Andreas Odermatt: Nidwalden (Ennetmoos) wechselt sich mit Surental
    (St. Erhard) ab; Zofingen (St. Erhard) ist derselbe wie Surental."""
    tage = [f"2024-{4 + i // 4:02d}-{1 + 7 * (i % 4):02d}" for i in range(12)]
    auftritte = {"nidwalden": [(t, f"f{i}") for i, t in enumerate(tage) if i % 2 == 0],
                 "surental": [(t, f"f{i}") for i, t in enumerate(tage) if i % 2 == 1],
                 "zofingen": [(f"2025-0{m}-01", f"z{m}") for m in range(3, 10)]}
    wohnorte = {"nidwalden": {"ennetmoos"}, "surental": {"sterhard"}, "zofingen": {"sterhard"}}
    gruppen = herkunft_gruppen(auftritte, wohnorte)
    assert {"surental", "zofingen"} in gruppen and {"nidwalden"} in gruppen


def test_trenne_nach_herkunft_mit_block_am_selben_fest():
    sw = {"schuler": Schwinger(id="schuler", name="Alex Schuler", jahrgang=1998,
                               schwingklub="am Mythen", teilverband="Innerschweiz", quellen=_P)}
    idx = baue_namensindex([{"id": "schuler", "name": "Alex Schuler"}])
    ev = _events("2026-05-01", "2026-05-08", "2026-05-15")
    rl = {"e0": {"eintraege": [{"name": "Schuler Alex", "schwingklub": "am Mythen", "punkte": 19.75},
                               {"name": "Schuler Alex", "schwingklub": "Einsiedeln", "punkte": 18.5}]},
          "e1": {"eintraege": [{"name": "Schuler Alex", "schwingklub": "am Mythen", "punkte": 10.0}]},
          "e2": {"eintraege": [{"name": "Schuler Alex", "schwingklub": "Einsiedeln", "punkte": 9.75}]}}
    zuordnung, neue, block, bericht = trenne_nach_herkunft(rl, ev, idx.finde, sw, {}, {})
    t = namens_tokens("Alex Schuler")
    vetter = next(iter(neue))
    assert vetter.endswith("|einsiedeln") and neue[vetter]["namensvetter_von"] == "schuler"
    assert zuordnung == {("e2", t): vetter}               # e1 bleibt beim Porträt
    assert block == {("e0", t, 19.75): "schuler", ("e0", t, 18.5): vetter}
    assert bericht["personen_getrennt"] == 1
