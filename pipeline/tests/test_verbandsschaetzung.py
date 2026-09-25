"""P6: Teilverband der Schwinger ohne Porträt, geschätzt aus ihren Festen."""
from __future__ import annotations

from pipeline.labels import GangResultat
from pipeline.schema import Schwinger
from pipeline.verbandsschaetzung import schaetze_teilverbaende


def _gang(event, a, b):
    a, b = sorted((a, b))
    return GangResultat(
        event_id=event, datum="2025-06-01", schwinger_a_id=a, schwinger_b_id=b,
        symbol_a="+", note_a=None, symbol_b="o", note_b=None,
        ergebnis="sieg_a", fest_typ="kantonal",
    )


def _fest(event, teilnehmer):
    """Kette von Gängen, sodass jeder Teilnehmer mindestens einmal antritt."""
    return [_gang(event, x, y) for x, y in zip(teilnehmer, teilnehmer[1:])]


class _Kader:
    def __init__(self):
        self.schwinger: dict[str, Schwinger] = {}
        self.gaenge: list[GangResultat] = []

    def porträts(self, verband, n, praefix):
        ids = [f"{praefix}{i}|2000" for i in range(n)]
        for sid in ids:
            self.schwinger[sid] = Schwinger(id=sid, name=sid, teilverband=verband)
        return ids

    def stub(self, sid):
        self.schwinger[sid] = Schwinger(id=sid, name=sid)
        return sid

    def fest(self, event, teilnehmer):
        self.gaenge += _fest(event, teilnehmer)


def _kader_mit_pruefung(n_feste=6):
    """Genug Porträts auf klar zugeordneten Festen, damit die Selbstprüfung greift."""
    k = _Kader()
    bern = k.porträts("Bern", 60, "be")
    inner = k.porträts("Innerschweiz", 60, "is")
    for f in range(n_feste):
        k.fest(f"be{f}", bern)
        k.fest(f"is{f}", inner)
    return k, bern, inner


def test_stub_an_berner_festen_wird_bern():
    k, _, _ = _kader_mit_pruefung()
    k.stub("stub|?")
    for f in range(3):
        k.gaenge.append(_gang(f"be{f}", "stub|?", "be0|2000"))
    schaetzung, bericht = schaetze_teilverbaende(k.gaenge, k.schwinger)
    assert schaetzung["stub|?"] == "Bern"
    assert bericht["angewandt"] and bericht["trefferquote"] == 1.0


def test_zu_wenige_feste_ergeben_keine_schaetzung():
    """Ein oder zwei Feste reichen nicht: gemessen trifft ein einzelnes Fest nur 89.5 %."""
    k, _, _ = _kader_mit_pruefung()
    k.stub("stub|?")
    for f in range(2):
        k.gaenge.append(_gang(f"be{f}", "stub|?", "be0|2000"))
    assert "stub|?" not in schaetze_teilverbaende(k.gaenge, k.schwinger)[0]


def test_gemischte_feste_ergeben_keine_schaetzung():
    k, _, _ = _kader_mit_pruefung()
    k.stub("stub|?")
    for f in range(2):
        k.gaenge.append(_gang(f"be{f}", "stub|?", "be0|2000"))
        k.gaenge.append(_gang(f"is{f}", "stub|?", "is0|2000"))
    assert "stub|?" not in schaetze_teilverbaende(k.gaenge, k.schwinger)[0]


def test_porträt_verband_wird_nie_ueberschrieben():
    k, bern, _ = _kader_mit_pruefung()
    schaetzung, _ = schaetze_teilverbaende(k.gaenge, k.schwinger)
    assert not set(schaetzung) & set(bern)


def test_selbstpruefung_unter_der_schwelle_schaetzt_nichts():
    """Tragen Porträt-Schwinger an ihren Festen systematisch einen anderen
    Verband, taugt die Regel für diesen Datenstand nicht -- dann lieber keine
    Schätzung als eine falsche."""
    k, _, _ = _kader_mit_pruefung()
    # 20 "Innerschweizer" treten nur an Berner Festen an -> Selbstprüfung fällt.
    fremde = k.porträts("Innerschweiz", 20, "fremd")
    for f in range(6):
        for sid in fremde:
            k.gaenge.append(_gang(f"be{f}", sid, "be0|2000"))
    k.stub("stub|?")
    for f in range(3):
        k.gaenge.append(_gang(f"be{f}", "stub|?", "be0|2000"))
    schaetzung, bericht = schaetze_teilverbaende(k.gaenge, k.schwinger)
    assert bericht["trefferquote"] < 0.97
    assert schaetzung == {} and bericht["angewandt"] is False


def test_leave_one_out_zaehlt_den_eigenen_verband_nicht_mit():
    """Ohne Leave-one-out bestätigte sich jeder Schwinger in der Prüfung
    selbst. Hier tragen genau 10 Teilnehmer einen Verband (die Mindestzahl):
    zieht man den eigenen ab, bleiben 9 -- kein Fest zählt, keine Prüfaussage.
    Mit Selbstbestätigung wären es 10 "Treffer"."""
    k = _Kader()
    bern = k.porträts("Bern", 10, "be")
    stubs = [k.stub(f"s{i}|?") for i in range(12)]
    for f in range(5):
        k.fest(f"f{f}", bern + stubs)
    schaetzung, bericht = schaetze_teilverbaende(k.gaenge, k.schwinger)
    assert bericht["pruef_faelle"] == 0 and bericht["angewandt"] is False
    assert schaetzung == {}
