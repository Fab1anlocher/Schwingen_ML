"""Auswertung der Schlussranglisten: Kränze, Klub, Verband über den Klub."""
from __future__ import annotations

from pipeline.ranglisten import (
    Teilnahme,
    klub_je_schwinger,
    konsistenz,
    kraenze_je_schwinger,
    kranzfeste_ohne_kranz,
    kranzquote_ausreisser,
    kranzstatus_je_schwinger,
    teilnahmen_aus_ranglisten,
    verband_ueber_klub,
)
from pipeline.schema import Event, Schwinger

_PORTRAET = ["schlussgang.ch/portraet"]


def _t(sid, eid="e1", datum="2025-06-01", typ="kantonal", kranz=False, status=None,
       klub=None, abzeichen=0):
    return Teilnahme(schwinger_id=sid, event_id=eid, datum=datum, fest_typ=typ, rang="1",
                     punkte=57.0, kranz=kranz, status=status, schwingklub=klub, wohnort=None,
                     senne_turner=None, abzeichen=abzeichen)


def test_kraenze_gesamt_und_je_festtyp():
    k = kraenze_je_schwinger([
        _t("a", "e1", kranz=True), _t("a", "e2", typ="berg", kranz=True), _t("a", "e3"),
        _t("b", "e1"),
    ])
    assert k["a"] == {"gesamt": 2, "nach_typ": {"kantonal": 1, "berg": 1}}
    assert k["b"] == {"gesamt": 0, "nach_typ": {}}


def test_juengster_klub_zaehlt():
    klubs = klub_je_schwinger([_t("a", "e1", "2024-05-01", klub="Alt"),
                               _t("a", "e2", "2025-05-01", klub="Neu"),
                               _t("a", "e3", "2025-06-01", klub=None)])
    assert klubs == {"a": "Neu"}


def test_kranzstatus_rechnet_den_ausgang_des_fests_mit():
    """Ramseier: mit ** zum ESAF, dort Neueidgenosse -> danach Eidgenosse."""
    ks = kranzstatus_je_schwinger([
        _t("ramseier", abzeichen=2, typ="eidgenoessisch", kranz=True, status="Neueidgenosse"),
        _t("neu", abzeichen=0, kranz=True, status="Neukranzer"),
        _t("ohne", abzeichen=0),
    ])
    assert ks == {"ramseier": "eidgenosse", "neu": "kranzer"}


def _sw(sid, tv=None, kanton=None, klub=None, portraet=True, jahrgang=None):
    return Schwinger(id=sid, name=sid, teilverband=tv, kanton=kanton, schwingklub=klub,
                     jahrgang=jahrgang, quellen=_PORTRAET if portraet else ["pdf"])


def test_verband_ueber_klub_mit_leave_one_out_pruefung():
    schwinger = {f"p{i}": _sw(f"p{i}", "Bern", "Emmental", "Zäziwil") for i in range(3)}
    schwinger["stub"] = _sw("stub", portraet=False)
    klubs = {"p0": "Zäziwil", "p1": "Zäziwil", "p2": "Zäziwil", "stub": "Zäziwil"}
    zuordnung, bericht = verband_ueber_klub(klubs, schwinger)
    assert zuordnung == {"stub": ("Bern", "Emmental")}
    assert bericht["pruef_faelle"] == 3 and bericht["trefferquote"] == 1.0


def test_klub_ohne_bekannte_mitglieder_ergibt_keine_zuordnung():
    schwinger = {"stub": _sw("stub", portraet=False)}
    zuordnung, bericht = verband_ueber_klub({"stub": "Unbekannt"}, schwinger)
    assert zuordnung == {} and bericht["pruef_faelle"] == 0


def test_konsistenz_meldet_kranzgewinner_ohne_portraet():
    schwinger = {"p": _sw("p", "Bern", klub="Zäziwil"), "s": _sw("s", portraet=False)}
    k = kraenze_je_schwinger([_t("p", kranz=True), _t("s", kranz=True)])
    bericht = konsistenz(k, {"p": "Zäziwil"}, schwinger)
    assert bericht["kranzgewinner_ohne_porträt"] == 1 and bericht["klub_wie_porträt"] == 1.0


def test_kranzfest_ohne_einen_einzigen_kranz_faellt_auf():
    ohne = kranzfeste_ohne_kranz([_t("a", "kant", typ="kantonal"), _t("b", "reg", typ="regional"),
                                  _t("c", "berg", typ="berg", kranz=True)])
    assert ohne == ["kant"]


def test_kranzquote_ausserhalb_der_ueblichen_15_bis_18_prozent_faellt_auf():
    # 100 Teilnehmer: 16 Kränze normal, 30 zu viele; Regionalfest zählt nicht.
    normal = [_t(f"n{i}", "normal", kranz=i < 16) for i in range(100)]
    zu_viel = [_t(f"z{i}", "zuviel", typ="berg", kranz=i < 30) for i in range(100)]
    regional = [_t(f"r{i}", "reg", typ="regional", kranz=i < 50) for i in range(100)]
    assert kranzquote_ausreisser(normal + zu_viel + regional) == [("zuviel", 0.3)]


def test_namensaufloesung_mit_jahrgang_trennt_namensvettern():
    """"Müller Roman (2009)": zwei Porträts gleichen Namens -- der Jahrgang entscheidet."""
    schwinger = {"roman muller|2009": Schwinger(id="roman muller|2009", name="Roman Müller", jahrgang=2009),
                 "roman muller|1995": Schwinger(id="roman muller|1995", name="Roman Müller", jahrgang=1995)}
    events = {"e1": Event(id="e1", name="Fest", datum="2025-06-01", typ="kantonal", quelle="x")}
    roh = {"e1": {"eintraege": [{"name": "Müller Roman (2009)", "punkte": 57.0, "kranz": True},
                                {"name": "Niemand Unbekannt", "punkte": 50.0}]},
           "e2": {"eintraege": [{"name": "Müller Roman (2009)", "punkte": 57.0}]},  # Fest unbekannt
           "e3": {"fehler": "RanglisteUnlesbar"}}
    teilnahmen, bericht = teilnahmen_aus_ranglisten(roh, {**events, "e3": events["e1"]},
                                                    lambda name: None, schwinger)
    assert [t.schwinger_id for t in teilnahmen] == ["roman muller|2009"]
    assert bericht["n_nicht_lesbar"] == 1 and bericht["anteil_namen_aufgeloest"] == 0.5
