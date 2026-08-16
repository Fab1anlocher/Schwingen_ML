"""Teilnehmerkreis kommender Feste (pipeline/teilnehmerkreis.py).

Ohne diese Einschränkung zeigt die Feste-Seite an jedem Fest dieselben
national stärksten Schwinger. Real passiert: am Nordwestschweizer
Schwingfest Mümliswil standen sechs Schwinger aus Bern und der
Nordostschweiz -- kein einziger davon startberechtigt.
"""
from __future__ import annotations

from dataclasses import dataclass

import pytest

from pipeline.teilnehmerkreis import (
    DOMINANZ_SCHWELLE,
    basisname,
    bestimme_teilnehmerkreis,
    teilverband_aus_name,
)


@dataclass
class _Schwinger:
    teilverband: str | None


@dataclass
class _Event:
    id: str
    name: str
    datum: str


@dataclass
class _Gang:
    event_id: str
    schwinger_a_id: str
    schwinger_b_id: str


def _feld(event_id: str, verbaende: list[str]):
    """Ein Fest mit je einem Schwinger pro Eintrag, paarweise verbunden."""
    schwinger = {f"{event_id}-s{i}": _Schwinger(tv) for i, tv in enumerate(verbaende)}
    ids = list(schwinger)
    gaenge = [_Gang(event_id, ids[i], ids[(i + 1) % len(ids)]) for i in range(len(ids))]
    return schwinger, gaenge


def test_kreis_kommt_aus_der_vorausgabe_auch_bei_regionalfesten():
    """Regionalfeste sind zu ~85 % von einem Teilverband dominiert, ihr Name
    nennt aber nur einen Ort -- nur die Vorausgabe verrät den Kreis."""
    schwinger, gaenge = _feld("ev-2025", ["Innerschweiz"] * 18 + ["Bern"] * 2)
    events = [_Event("ev-2025", "Herbstschwinget Unteriberg 2025", "2025-10-05")]
    kommende = [{"name": "Herbstschwinget Unteriberg 2026", "typ": "regional"}]

    bestimme_teilnehmerkreis(kommende, events, gaenge, schwinger)
    assert kommende[0]["teilverband"] == "Innerschweiz"
    assert kommende[0]["teilverband_quelle"] == "vorausgabe"


def test_gemischtes_feld_bleibt_offen():
    """Bergfeste liegen bei ~43 % grösstem Teilverband und dürfen nicht
    gefiltert werden -- die Schwelle erledigt das ohne Sonderregel."""
    schwinger, gaenge = _feld(
        "ev-2025", ["Innerschweiz"] * 9 + ["Bern"] * 6 + ["Nordostschweiz"] * 5
    )
    events = [_Event("ev-2025", "Schwägalp-Schwinget 2025", "2025-08-17")]
    kommende = [{"name": "Schwägalp-Schwinget 2026", "typ": "berg"}]

    bestimme_teilnehmerkreis(kommende, events, gaenge, schwinger)
    assert kommende[0]["teilverband"] is None
    assert kommende[0]["teilverband_quelle"] == "vorausgabe_offen"


def test_ohne_vorausgabe_greift_das_namensmuster():
    kommende = [{"name": "Nordwestschweizer Schwingfest Mümliswil 2026", "typ": "teilverband"}]
    bestimme_teilnehmerkreis(kommende, [], [], {})
    assert kommende[0]["teilverband"] == "Nordwestschweiz"
    assert kommende[0]["teilverband_quelle"] == "namensmuster"


def test_offener_fest_typ_wird_ohne_vorausgabe_nicht_eingeschraenkt():
    kommende = [{"name": "Kilchberger Schwinget Kilchberg 2026", "typ": "eidgenoessisch"}]
    bestimme_teilnehmerkreis(kommende, [], [], {})
    assert kommende[0]["teilverband"] is None
    assert kommende[0]["teilverband_quelle"] == "offen"


def test_zu_kleine_stichprobe_schraenkt_nicht_ein():
    schwinger, gaenge = _feld("ev-2025", ["Bern"] * 4)
    events = [_Event("ev-2025", "Kleiner Schwinget Irgendwo 2025", "2025-06-01")]
    kommende = [{"name": "Kleiner Schwinget Irgendwo 2026", "typ": "regional"}]
    bestimme_teilnehmerkreis(kommende, events, gaenge, schwinger)
    assert kommende[0]["teilverband"] is None


def test_vorausgabe_schlaegt_namensmuster():
    """Der Name kann in die Irre führen; gemessene Teilnehmer nicht."""
    schwinger, gaenge = _feld("ev-2025", ["Bern"] * 20)
    events = [_Event("ev-2025", "Zuger Herbstschwinget Musterhausen 2025", "2025-09-01")]
    kommende = [{"name": "Zuger Herbstschwinget Musterhausen 2026", "typ": "regional"}]
    # Das Namensmuster ("Zuger") würde Innerschweiz sagen.
    assert teilverband_aus_name(kommende[0]["name"], "regional") == "Innerschweiz"
    bestimme_teilnehmerkreis(kommende, events, gaenge, schwinger)
    assert kommende[0]["teilverband"] == "Bern"
    assert kommende[0]["teilverband_quelle"] == "vorausgabe"


def test_ortswechsel_bricht_die_zuordnung_ueber_die_vorausgabe():
    """Kantonal- und Teilverbandsfeste wechseln jährlich den Austragungsort --
    ihr Basisname ändert sich mit, die Vorausgabe ist nicht auffindbar. Genau
    dafür gibt es das Namensmuster als zweite Stufe."""
    schwinger, gaenge = _feld("ev-2025", ["Nordwestschweiz"] * 20)
    events = [_Event("ev-2025", "Nordwestschweizer Schwingfest Lenzburg 2025", "2025-08-10")]
    kommende = [{"name": "Nordwestschweizer Schwingfest Mümliswil 2026", "typ": "teilverband"}]
    bestimme_teilnehmerkreis(kommende, events, gaenge, schwinger)
    assert kommende[0]["teilverband"] == "Nordwestschweiz"
    assert kommende[0]["teilverband_quelle"] == "namensmuster"


@pytest.mark.parametrize("name,typ,erwartet", [
    ("Solothurner Kantonalschwingfest Grenchen 2026", "kantonal", "Nordwestschweiz"),
    ("Bern-Jurassisches Schwingfest Werdtberg 2026", "kantonal", "Bern"),
    ("Toggenburger Herbstschwinget Bütschwil 2026", "regional", "Nordostschweiz"),
    ("Schwägalp-Schwinget 2026", "berg", None),
    ("Herbstschwinget Unteriberg 2026", "regional", None),
])
def test_namensmuster_grenzfaelle(name, typ, erwartet):
    assert teilverband_aus_name(name, typ) == erwartet


def test_basisname_entfernt_nur_die_jahreszahl():
    assert basisname("Herbstschwinget Unteriberg 2026") == "herbstschwinget unteriberg"
    assert basisname("Schwägalp-Schwinget 2026") == "schwägalp-schwinget"


def test_schwelle_ist_dokumentiert_und_konservativ():
    # Bei 60 % ergaben sich ueber alle 165 Fest-Paare der Datenbasis
    # 139 Einschraenkungen und keine einzige falsche.
    assert DOMINANZ_SCHWELLE == 0.60
