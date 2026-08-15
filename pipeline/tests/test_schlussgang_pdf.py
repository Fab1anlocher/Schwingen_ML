"""Tests für den Statistik-PDF-Parser (schlussgang_pdf.py), insb. die
Kranz-Sterne-Erkennung in der Kopfzeile (vorher geparst und sofort wieder
verworfen -- jetzt Grundlage für die Kranz-Zählung auf der Schwinger-Seite)."""
from __future__ import annotations

from pipeline.scrape.schlussgang_pdf import parse_pdf_bytes, tabellen_bloecke


def _wort(text: str, top: float, x0: float) -> dict:
    return {"text": text, "top": top, "x0": x0}


def test_kopfzeile_mit_stern_markiert_kranz():
    woerter = [
        _wort("1", 10, 5), _wort("Hans", 10, 20), _wort("Meier", 10, 50),
        _wort("*", 10, 90), _wort("57.50", 10, 110),
        _wort("+", 25, 5), _wort("Peter", 25, 20), _wort("Muster", 25, 60), _wort("9.75", 25, 110),
    ]
    bloecke = tabellen_bloecke([woerter])
    assert len(bloecke) == 1
    assert bloecke[0]["name"] == "Hans Meier"
    assert bloecke[0]["kranz"] is True
    assert bloecke[0]["total"] == 57.50


def test_kopfzeile_ohne_stern_kein_kranz():
    woerter = [
        _wort("2", 10, 5), _wort("Lisa", 10, 20), _wort("Kunz", 10, 50), _wort("55.00", 10, 110),
        _wort("o", 25, 5), _wort("Beat", 25, 20), _wort("Frei", 25, 60), _wort("7.00", 25, 110),
    ]
    bloecke = tabellen_bloecke([woerter])
    assert len(bloecke) == 1
    assert bloecke[0]["name"] == "Lisa Kunz"
    assert bloecke[0]["kranz"] is False


def test_parse_pdf_bytes_gibt_kranz_pro_gang_weiter(monkeypatch):
    woerter = [
        _wort("1", 10, 5), _wort("Hans", 10, 20), _wort("Meier", 10, 50),
        _wort("*", 10, 90), _wort("57.50", 10, 110),
        _wort("+", 25, 5), _wort("Peter", 25, 20), _wort("Muster", 25, 60), _wort("9.75", 25, 110),
    ]
    monkeypatch.setattr(
        "pipeline.scrape.schlussgang_pdf.extrahiere_woerter", lambda pdf_bytes: [woerter]
    )
    eintraege = parse_pdf_bytes(b"dummy", event_id="ev1", datum="2024-05-01", fest_typ="kantonal")
    assert len(eintraege) == 1
    assert eintraege[0]["kranz"] is True
    assert eintraege[0]["schwinger_name"] == "Hans Meier"


# --- Kopfzeilen-Varianten: der Stern steht nicht immer an derselben Stelle ---
# Regression: die alte Prüfung sah nur das letzte Token VOR dem Punktetotal
# und übersah damit den Grossteil der Kränze (650 gezählt statt ~3'000 plausibel).

def _kopf(*tokens: str) -> list[dict]:
    """Kopfzeile + ein Gang, Tokens mit aufsteigendem x0."""
    woerter = [_wort(t, 10, 5 + 30 * i) for i, t in enumerate(tokens)]
    woerter += [_wort("+", 25, 5), _wort("Peter", 25, 20), _wort("Muster", 25, 60),
                _wort("9.75", 25, 110)]
    return woerter


def test_stern_zwischen_name_und_total():
    b = tabellen_bloecke([_kopf("1", "Hans", "Meier", "*", "57.50")])[0]
    assert b["kranz"] is True and b["name"] == "Hans Meier" and b["total"] == 57.50


def test_stern_hinter_dem_total():
    """Vorher fatal: das Total war nicht mehr letztes Token, landete deshalb
    ungelesen im Namen -- der Schwinger war danach nicht auflösbar."""
    b = tabellen_bloecke([_kopf("1", "Hans", "Meier", "57.50", "*")])[0]
    assert b["kranz"] is True
    assert b["name"] == "Hans Meier"
    assert b["total"] == 57.50


def test_stern_klebt_am_namen():
    b = tabellen_bloecke([_kopf("1", "Hans", "Meier**", "57.50")])[0]
    assert b["kranz"] is True and b["name"] == "Hans Meier" and b["total"] == 57.50


def test_mehrere_sterne_als_eigene_token():
    b = tabellen_bloecke([_kopf("1", "Hans", "Meier", "*", "*", "57.50")])[0]
    assert b["kranz"] is True and b["name"] == "Hans Meier"


def test_unicode_sternvarianten():
    for zeichen in ("∗", "✱", "⁎", "＊"):
        b = tabellen_bloecke([_kopf("1", "Hans", "Meier", zeichen, "57.50")])[0]
        assert b["kranz"] is True, zeichen
        assert b["name"] == "Hans Meier"


def test_ohne_stern_weiterhin_kein_kranz():
    b = tabellen_bloecke([_kopf("2", "Lisa", "Kunz", "55.00")])[0]
    assert b["kranz"] is False and b["name"] == "Lisa Kunz" and b["total"] == 55.00


def test_stern_am_gegnernamen_verfaelscht_den_namen_nicht():
    """Klebte ein Stern am Gegnernamen, war der Name nicht auflösbar und der
    Gang fiel still aus dem Training."""
    woerter = [
        _wort("1", 10, 5), _wort("Hans", 10, 20), _wort("Meier", 10, 50), _wort("57.50", 10, 110),
        _wort("+", 25, 5), _wort("Peter", 25, 20), _wort("Muster*", 25, 60), _wort("9.75", 25, 110),
    ]
    b = tabellen_bloecke([woerter])[0]
    assert b["gaenge"][0]["gegner_name"] == "Peter Muster"
    assert b["gaenge"][0]["note"] == 9.75
