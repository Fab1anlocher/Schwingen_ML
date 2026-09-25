"""Parser der Schlussranglisten (offizielle ESV-Listen über schlussgang.ch).

Wortlisten wie pdfplumber sie liefert, nachgebaut nach vermessenen echten
Ranglisten (x-Positionen aus Oberaargau 2025, ESAF 2025, Urner 2026). Echte
PDFs liegen bewusst nicht im Repo (Copyright ESV).
"""
from __future__ import annotations

from pipeline.scrape.schlussgang_rangliste import mit_kranz, parse_seiten


def _w(text, x0, top):
    return {"text": text, "x0": float(x0), "top": float(top)}


def _zeile(top, *woerter):
    return [_w(t, x, top) for t, x in woerter]


KOPF = _zeile(99, ("Rang", 40), ("Punkte", 71), ("Resultat", 112), ("Name", 159), ("Vorname", 188),
              ("Wohnort", 291), ("Schwingklub", 431), ("Status", 529))


def _seite(*zeilen):
    return [w for z in zeilen for w in z]


def test_standardzeile_mit_stern_senn_und_status():
    seite = _seite(KOPF, _zeile(114, ("1", 39), ("58.75", 78), ("-+++++", 119), ("Moser", 159),
                                ("Michael,", 188), ("S", 226), ("**", 236), ("Biglen", 290),
                                ("Zäziwil", 430), ("Kranz", 528)))
    [e] = parse_seiten([seite])
    assert e == {"rang": "1", "punkte": 58.75, "resultat": "-+++++", "name": "Moser Michael",
                 "senne_turner": "senne", "abzeichen": 2, "wohnort": "Biglen",
                 "schwingklub": "Zäziwil", "status": "Kranz"}


def test_wohnort_und_klub_werden_ueber_die_spalte_getrennt():
    """Im Fliesstext nicht trennbar: "Röthenbach im Emmental Siehen"."""
    seite = _seite(KOPF, _zeile(114, ("7a", 39), ("55.75", 81), ("-++--+", 126), ("Stucki", 159),
                                ("Marcel", 194), ("(1),", 225), ("S", 242), ("*", 251),
                                ("Röthenbach", 291), ("im", 345), ("Emmental", 358),
                                ("Rapperswil", 431), ("u.", 481), ("Umgebung", 492)))
    [e] = parse_seiten([seite])
    assert e["name"] == "Stucki Marcel (1)"
    assert e["wohnort"] == "Röthenbach im Emmental"
    assert e["schwingklub"] == "Rapperswil u. Umgebung"
    assert e["senne_turner"] == "senne" and e["abzeichen"] == 1


def test_status_auf_eigener_zeile_gehoert_zur_rangzeile_darueber():
    """ESAF 2025: "Neueidgenosse" sitzt 3 Punkte tiefer und links der Kopfzeile."""
    seite = _seite(KOPF,
                   _zeile(141, ("3", 39), ("76.25", 72), ("o++-++-+", 108), ("Moser", 159),
                          ("Michael,", 188), ("S", 223), ("**", 232), ("Biglen", 291), ("Zäziwil", 431)),
                   _zeile(144, ("Neueidgenosse", 520)),
                   _zeile(155, ("4a", 39), ("76.00", 72), ("o+++o+++", 106), ("Aeschbacher", 159),
                          ("Matthias,", 214), ("S", 255), ("***", 264), ("Rüegsauschachen", 291),
                          ("Sumiswald", 431)))
    eintraege = parse_seiten([seite])
    assert [e["status"] for e in eintraege] == ["Neueidgenosse", None]


def test_zeile_ohne_klub_und_ohne_senn_turner():
    seite = _seite(KOPF, _zeile(114, ("13c", 39), ("55.00", 78), ("o++o+o", 119), ("Koch", 159),
                                ("Nico,", 188), ("Gonten", 291)))
    [e] = parse_seiten([seite])
    assert e["schwingklub"] is None and e["senne_turner"] is None and e["wohnort"] == "Gonten"


def test_angeklebtes_resultat_und_folgeseite_ohne_kopf():
    """Urner Rangliste 2026 klebt Punkte und Resultat zusammen; Folgeseiten
    ohne Kopfzeile nutzen die Spalten der letzten Kopfzeile."""
    seite1 = _seite(KOPF, _zeile(114, ("1", 49), ("58.75S-+++++", 67), ("Bissig", 159),
                                 ("Lukas,", 188), ("S", 210), ("***", 219), ("Attinghausen", 291),
                                 ("Attinghausen", 431), ("Kranz", 529)))
    seite2 = _seite(_zeile(40, ("33c", 39), ("8.50", 81), ("o", 132), ("Bösiger", 159),
                           ("Kenny,", 194), ("Oberbipp", 291), ("Herzogenbuchsee", 431)))
    e1, e2 = parse_seiten([seite1, seite2])
    assert e1["punkte"] == 58.75 and e1["resultat"] == "-+++++" and e1["name"] == "Bissig Lukas"
    assert e2["name"] == "Bösiger Kenny" and e2["schwingklub"] == "Herzogenbuchsee"


def test_legende_und_fusszeile_werden_ignoriert():
    seite = _seite(KOPF,
                   _zeile(114, ("1", 39), ("58.75", 78), ("-+++++", 119), ("Moser", 159),
                          ("Michael,", 188), ("Biglen", 291), ("Zäziwil", 431)),
                   _zeile(256, ("*", 38), ("Kantonal-", 42), ("bzw.", 75), ("Gauverbandskranzschwinger", 92)),
                   _zeile(800, ("Inkwil", 38), ("Quelle:", 222), ("ESV", 247), ("07.06.2025", 532)))
    assert len(parse_seiten([seite])) == 1


def test_seite_ohne_kopfzeile_und_ohne_vorherige_ergibt_nichts():
    seite = _zeile(114, ("1", 39), ("58.75", 78), ("-+++++", 119), ("Moser", 159), ("Michael,", 188))
    assert parse_seiten([seite]) == []


# --- Kranz ---------------------------------------------------------------------

def _e(punkte, status=None):
    return {"punkte": punkte, "status": status}


def test_kranz_ab_der_schwelle_des_niedrigsten_markierten():
    eintraege = mit_kranz([_e(58.0, "Kranz"), _e(56.5, "Neukranzer"), _e(56.25), _e(55.0)])
    assert [e["kranz"] for e in eintraege] == [True, True, False, False]


def test_esaf_markiert_nur_neueidgenossen_bisherige_zaehlen_trotzdem():
    """ESAF 2025: 17 Neueidgenossen markiert, 23 bisherige Eidgenossen über der
    Schwelle ohne Status -- zusammen 40 Kränze (14.9 %)."""
    eintraege = mit_kranz([_e(77.0), _e(76.25, "Neueidgenosse"), _e(74.5, "Neueidgenosse"),
                           _e(74.5), _e(74.25)])
    assert [e["kranz"] for e in eintraege] == [True, True, True, True, False]


def test_ohne_jede_markierung_kein_kranz():
    """Regionalfeste und Kilchberg vergeben keinen Kranz."""
    assert not any(e["kranz"] for e in mit_kranz([_e(58.0), _e(57.0)]))
