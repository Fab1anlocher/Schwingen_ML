"""Tests für den Statistik-PDF-Parser (schlussgang_pdf.py), insb. die
Statusabzeichen-Erkennung in der Kopfzeile. Der Stern markiert den Kranzstatus
des Schwingers (Kranzer/Eidgenosse), NICHT einen Kranzgewinn am Fest --
s. pipeline/scrape/schlussgang_pdf.py."""
from __future__ import annotations

from pipeline.scrape.schlussgang_pdf import parse_pdf_bytes, tabellen_bloecke


def _wort(text: str, top: float, x0: float) -> dict:
    return {"text": text, "top": top, "x0": x0}


def test_kopfzeile_mit_stern_markiert_abzeichen():
    woerter = [
        _wort("1", 10, 5), _wort("Hans", 10, 20), _wort("Meier", 10, 50),
        _wort("*", 10, 90), _wort("57.50", 10, 110),
        _wort("+", 25, 5), _wort("Peter", 25, 20), _wort("Muster", 25, 60), _wort("9.75", 25, 110),
    ]
    bloecke = tabellen_bloecke([woerter])
    assert len(bloecke) == 1
    assert bloecke[0]["name"] == "Hans Meier"
    assert bloecke[0]["status_abzeichen"] is True
    assert bloecke[0]["total"] == 57.50


def test_kopfzeile_ohne_stern_kein_abzeichen():
    woerter = [
        _wort("2", 10, 5), _wort("Lisa", 10, 20), _wort("Kunz", 10, 50), _wort("55.00", 10, 110),
        _wort("o", 25, 5), _wort("Beat", 25, 20), _wort("Frei", 25, 60), _wort("7.00", 25, 110),
    ]
    bloecke = tabellen_bloecke([woerter])
    assert len(bloecke) == 1
    assert bloecke[0]["name"] == "Lisa Kunz"
    assert bloecke[0]["status_abzeichen"] is False


def test_parse_pdf_bytes_gibt_abzeichen_pro_gang_weiter(monkeypatch):
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
    assert eintraege[0]["status_abzeichen"] is True
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
    assert b["status_abzeichen"] is True and b["name"] == "Hans Meier" and b["total"] == 57.50


def test_stern_hinter_dem_total():
    """Vorher fatal: das Total war nicht mehr letztes Token, landete deshalb
    ungelesen im Namen -- der Schwinger war danach nicht auflösbar."""
    b = tabellen_bloecke([_kopf("1", "Hans", "Meier", "57.50", "*")])[0]
    assert b["status_abzeichen"] is True
    assert b["name"] == "Hans Meier"
    assert b["total"] == 57.50


def test_stern_klebt_am_namen():
    b = tabellen_bloecke([_kopf("1", "Hans", "Meier**", "57.50")])[0]
    assert b["status_abzeichen"] is True and b["name"] == "Hans Meier" and b["total"] == 57.50


def test_mehrere_sterne_als_eigene_token():
    b = tabellen_bloecke([_kopf("1", "Hans", "Meier", "*", "*", "57.50")])[0]
    assert b["status_abzeichen"] is True and b["name"] == "Hans Meier"


def test_unicode_sternvarianten():
    for zeichen in ("∗", "✱", "⁎", "＊"):
        b = tabellen_bloecke([_kopf("1", "Hans", "Meier", zeichen, "57.50")])[0]
        assert b["status_abzeichen"] is True, zeichen
        assert b["name"] == "Hans Meier"


def test_ohne_stern_weiterhin_kein_abzeichen():
    b = tabellen_bloecke([_kopf("2", "Lisa", "Kunz", "55.00")])[0]
    assert b["status_abzeichen"] is False and b["name"] == "Lisa Kunz" and b["total"] == 55.00


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


def test_rang_wird_mitgefuehrt():
    """Der Rang war nur Zeilenmarker und wurde verworfen. Ohne ihn lässt sich
    nicht prüfen, ob die Sterne auf den vorderen Rängen sitzen (Kranzgewinn)
    oder über das Feld streuen (Statusabzeichen)."""
    b = tabellen_bloecke([_kopf("7", "Hans", "Meier", "*", "57.50")])[0]
    assert b["rang"] == "7"
    b2 = tabellen_bloecke([_kopf("3a", "Lisa", "Kunz", "55.00")])[0]
    assert b2["rang"] == "3a"


# --- Roadmap D4: Niederlage als Ziffer "0" (PDFs bis Anfang 2024) -------------

def test_niederlage_als_null_ist_gang_keine_kopfzeile():
    """Vorher war "0" ein Rang: jede Niederlage eröffnete einen falschen Block
    auf den Namen des Gegners, die folgenden Gänge hingen dann an ihm."""
    woerter = [
        _wort("8h", 10, 5), _wort("Heinzer", 10, 20), _wort("Ronny", 10, 60), _wort("27.50", 10, 110),
        _wort("0", 25, 5), _wort("Lemmenmeier", 25, 20), _wort("Lukas", 25, 60), _wort("8.50", 25, 110),
        _wort("+", 40, 5), _wort("Achermann", 40, 20), _wort("Christian", 40, 60), _wort("10.00", 40, 110),
        _wort("-", 55, 5), _wort("Heiniger", 55, 20), _wort("Marco", 55, 60), _wort("9.00", 55, 110),
        _wort("8k", 70, 5), _wort("Thalmann", 70, 20), _wort("Adrian", 70, 60), _wort("19.75", 70, 110),
        _wort("+", 85, 5), _wort("Hug", 85, 20), _wort("Jan", 85, 60), _wort("10.00", 85, 110),
        _wort("0", 100, 5), _wort("Fellmann", 100, 20), _wort("Roman", 100, 60), _wort("9.75", 100, 110),
    ]
    bloecke = tabellen_bloecke([woerter])
    assert [b["name"] for b in bloecke] == ["Heinzer Ronny", "Thalmann Adrian"]
    assert [g["symbol"] for g in bloecke[0]["gaenge"]] == ["o", "+", "-"]
    assert [g["symbol"] for g in bloecke[1]["gaenge"]] == ["+", "o"]
    # Gegenprobe: die Notensumme passt zum Punktetotal.
    assert all(abs(sum(g["note"] for g in b["gaenge"]) - b["total"]) < 0.01 for b in bloecke)


def test_parse_pdf_bytes_speichert_punktetotal(monkeypatch):
    woerter = [
        _wort("1", 10, 5), _wort("Hans", 10, 20), _wort("Meier", 10, 50), _wort("9.75", 10, 110),
        _wort("+", 25, 5), _wort("Peter", 25, 20), _wort("Muster", 25, 60), _wort("9.75", 25, 110),
    ]
    monkeypatch.setattr(
        "pipeline.scrape.schlussgang_pdf.extrahiere_woerter", lambda pdf_bytes: [woerter]
    )
    e = parse_pdf_bytes(b"x", event_id="ev1", datum="2023-05-01", fest_typ="regional")[0]
    assert e["punktetotal"] == 9.75 and e["note"] == 9.75


def test_punktetotal_pruefung_findet_falsch_zugeordnete_gaenge():
    from pipeline.scrape import punktetotal_pruefung

    def r(name, note, total, datum="2023-05-01"):
        return {"event_id": "f1", "datum": datum, "schwinger_name": name, "note": note,
                "punktetotal": total}
    roh = [r("A", 10.0, 19.75), r("A", 9.75, 19.75),            # passt
           r("B", 8.5, 8.5), r("B", 10.0, 8.5),                  # fremder Gang angehängt
           {"event_id": "f1", "datum": "2023-05-01", "schwinger_name": "C", "note": 9.0}]  # alter Cache
    p = punktetotal_pruefung(roh)
    assert p["bloecke_geprueft"] == 2 and p["abweichend"] == 1 and p["eintraege_ohne_total"] == 1
    assert p["je_jahr"]["2023"] == {"geprueft": 2, "abweichend": 1}


def test_rang_mit_zwei_buchstaben_eroeffnet_einen_block():
    # ESAF 2025: nach "15z" folgen "15aa", "15ab" -- früher unerkannt, die
    # Gänge hingen dann am Schwinger davor (Florian Aellen mit 24 Gängen).
    woerter = [
        _wort("15z", 10, 5), _wort("Aellen", 10, 20), _wort("Florian", 10, 50), _wort("63.25", 10, 110),
        _wort("+", 25, 5), _wort("Lang", 25, 20), _wort("Sven", 25, 60), _wort("10.00", 25, 110),
        _wort("15aa", 40, 5), _wort("Birchler", 40, 20), _wort("Fabian", 40, 60), _wort("62.75", 40, 110),
        _wort("-", 55, 5), _wort("Kramer", 55, 20), _wort("Dorian", 55, 60), _wort("8.75", 55, 110),
    ]
    bloecke = tabellen_bloecke([woerter])
    assert [b["name"] for b in bloecke] == ["Aellen Florian", "Birchler Fabian"]
    assert [len(b["gaenge"]) for b in bloecke] == [1, 1]
