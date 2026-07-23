"""Tests für den esv.ch-Rangliste-Parser (neue Primärquelle).

Kernpunkte: nur das höchste Gang-Panel (vollständige Schlussrangliste) parsen,
nicht die Zwischenrang-Panels; stabile uid/slug-Identität; Gang-Ergebnis aus
der win/draw/loss-Zellklasse."""
from __future__ import annotations

import pytest

pytest.importorskip("bs4")

from pipeline.scrape.esv_ranglisten import parse_rangliste

# Minimal-HTML im Format von esv.ch: zwei Gang-Panels (Zwischenstand nach Gang 1
# und vollständige Rangliste nach Gang 2). Der Parser darf NUR das Gang-2-Panel
# nehmen, sonst würde er Gänge doppelt zählen.
FIXTURE = """
<html><head><title>Beispiel-Schwinget vom 05.07.2026: Offizielle Rangliste</title></head>
<body>
<div id="anlass-tab-rangliste">
  <div class="rangliste-gang-panel" data-rl-gang="1">
    <table class="anlassRangliste"><tbody>
      <tr class="rang-row rang-expandable" data-uid="100">
        <td class="col-rang">1</td><td class="col-kranz"></td>
        <td class="col-name"><a href="https://esv.ch/schwingerportraets/Muster_Hans_Bern/">Muster Hans <span class="kranzkennung">***</span></a></td>
        <td class="col-verband">BKSV ML</td><td class="col-resultate">+</td><td class="col-punkte numeric">10.00</td>
      </tr>
      <tr class="rang-detail-row" data-detail-uid="100">
        <td class="gang-score-cell win"><span class="gang-sym">+</span><span class="gang-pt">10.00</span></td>
        <td class="col-name gang-gegner"><a href="https://esv.ch/schwingerportraets/Beispiel_Beat_Zug/">Beispiel Beat</a></td>
        <td class="col-verband gang-verband">ISV ZG</td>
      </tr>
    </tbody></table>
  </div>
  <div class="rangliste-gang-panel" data-rl-gang="2">
    <table class="anlassRangliste"><tbody>
      <tr class="rang-row rang-expandable" data-uid="100">
        <td class="col-rang">1</td><td class="col-kranz"><img src="/kranz.svg"></td>
        <td class="col-name"><a href="https://esv.ch/schwingerportraets/Muster_Hans_Bern/">Muster Hans <span class="kranzkennung">***</span></a></td>
        <td class="col-verband">BKSV ML</td><td class="col-resultate">+</td><td class="col-punkte numeric">20.00</td>
      </tr>
      <tr class="rang-detail-row" data-detail-uid="100">
        <td class="gang-score-cell win"><span class="gang-sym">+</span><span class="gang-pt">10.00</span></td>
        <td class="col-name gang-gegner"><a href="https://esv.ch/schwingerportraets/Beispiel_Beat_Zug/">Beispiel Beat</a></td>
        <td class="col-verband gang-verband">ISV ZG</td>
      </tr>
      <tr class="rang-detail-row" data-detail-uid="100">
        <td class="gang-score-cell draw"><span class="gang-sym">-</span><span class="gang-pt">8.75</span></td>
        <td class="col-name gang-gegner"><a href="https://esv.ch/schwingerportraets/Roth_Urs_Thun/">Roth Urs</a></td>
        <td class="col-verband gang-verband">BKSV OB</td>
      </tr>
      <tr class="rang-row rang-expandable" data-uid="200">
        <td class="col-rang">2</td><td class="col-kranz"></td>
        <td class="col-name"><a href="https://esv.ch/schwingerportraets/Beispiel_Beat_Zug/">Beispiel Beat <span class="kranzkennung">*</span></a></td>
        <td class="col-verband">ISV ZG</td><td class="col-resultate">o</td><td class="col-punkte numeric">18.00</td>
      </tr>
      <tr class="rang-detail-row" data-detail-uid="200">
        <td class="gang-score-cell loss"><span class="gang-sym">o</span><span class="gang-pt">8.00</span></td>
        <td class="col-name gang-gegner"><a href="https://esv.ch/schwingerportraets/Muster_Hans_Bern/">Muster Hans</a></td>
        <td class="col-verband gang-verband">BKSV ML</td>
      </tr>
    </tbody></table>
  </div>
</div>
</body></html>
"""


def test_event_metadaten():
    rl = parse_rangliste(FIXTURE, anlass_id="42")
    assert rl.anlass_id == "42"
    assert rl.name == "Beispiel-Schwinget"
    assert rl.datum == "2026-07-05"


def test_nur_hoechstes_gang_panel():
    # Gang-2-Panel: 2 Schwinger. Gang-1-Panel (1 Schwinger) muss ignoriert werden.
    rl = parse_rangliste(FIXTURE)
    assert len(rl.schwinger) == 2
    uids = {s.uid for s in rl.schwinger}
    assert uids == {"100", "200"}


def test_schwinger_felder_und_identitaet():
    rl = parse_rangliste(FIXTURE)
    hans = next(s for s in rl.schwinger if s.uid == "100")
    assert hans.name == "Muster Hans"
    assert hans.slug == "Muster_Hans_Bern"
    assert hans.verband == "BKSV ML"
    assert hans.karriere_sterne == 3
    assert hans.punkte_total == 20.00
    assert hans.kranz_hier is True  # col-kranz enthält ein <img> im Gang-2-Panel
    beat = next(s for s in rl.schwinger if s.uid == "200")
    assert beat.karriere_sterne == 1
    assert beat.kranz_hier is False


def test_gaenge_ergebnis_und_gegner():
    rl = parse_rangliste(FIXTURE)
    # Hans hat im Gang-2-Panel 2 Gänge (win + draw), Beat 1 (loss).
    hans_g = [g for g in rl.gaenge if g.schwinger_uid == "100"]
    assert len(hans_g) == 2
    win = next(g for g in hans_g if g.ergebnis == "win")
    assert win.symbol == "+" and win.punkte == 10.00
    assert win.gegner_slug == "Beispiel_Beat_Zug"
    assert win.gegner_verband == "ISV ZG"
    draw = next(g for g in hans_g if g.ergebnis == "draw")
    assert draw.symbol == "-"
    beat_g = [g for g in rl.gaenge if g.schwinger_uid == "200"]
    assert len(beat_g) == 1 and beat_g[0].ergebnis == "loss" and beat_g[0].symbol == "o"


def test_leeres_html_bleibt_leer():
    rl = parse_rangliste("<html><body>nix</body></html>")
    assert rl.schwinger == [] and rl.gaenge == []


# --- Fest-Klassifikator + Jahres-Index ---------------------------------------
from pipeline.scrape.esv_ranglisten import fest_stufe, parse_jahr_index  # noqa: E402


def test_fest_stufe_eidgenoessisch():
    assert fest_stufe("Eidgenössisches Schwing- und Älplerfest (ESAF)") == "eidgenoessisch"
    assert fest_stufe("Kilchberger Schwinget") == "eidgenoessisch"
    assert fest_stufe("Unspunnen-Schwinget") == "eidgenoessisch"


def test_fest_stufe_kein_falscher_eidg_treffer():
    # "Eidg." im Namen, aber KEIN Schwingfest -> nicht eidgenössisch.
    assert fest_stufe("Eidg. Schwinger-Fussballturnier") == "regional"


def test_fest_stufe_berg_teilverband_kantonal_regional():
    assert fest_stufe("Rigi Schwinget") == "berg"
    assert fest_stufe("59. Weissenstein-Schwinget") == "berg"
    assert fest_stufe("Nordostschweizer Schwingfest") == "teilverband"
    assert fest_stufe("Bernisch-kantonales Schwingfest") == "teilverband"
    assert fest_stufe("Zürcher Kantonalschwingfest") == "kantonal"
    assert fest_stufe("Emmentalisches Schwingfest") == "kantonal"  # Berner Gauverband
    assert fest_stufe("Abendschwinget Baar") == "regional"


_INDEX_FIXTURE = """
<table><tbody>
<tr class="aktiv" id="anlass1226">
  <td class="datum"><time datetime="2010-12-05">05.12<span class="year">.2010</span></time></td>
  <td class="name"><a href="?anlass=1226">73. Niklausschwinget</a></td>
  <td class="typ">aktiv</td><td class="ort">Dietikon ZH</td>
</tr>
<tr class="jung" id="anlass1452">
  <td class="datum"><time datetime="2010-12-05">05.12</time></td>
  <td class="name"><a href="?anlass=1452">Niklausschwinget</a></td>
  <td class="typ">jung</td><td class="ort">Plaffeien FR</td>
</tr>
<tr class="aktiv" id="anlass999">
  <td class="datum"><time datetime="2010-08-22">22.08</time></td>
  <td class="name"><a href="?anlass=999">Eidgenössisches Schwing- und Älplerfest</a></td>
  <td class="typ">aktiv</td><td class="ort">Frauenfeld TG</td>
</tr>
</tbody></table>
"""


def test_parse_jahr_index_felder_und_kategorie():
    refs = parse_jahr_index(_INDEX_FIXTURE)
    assert len(refs) == 3
    r = next(x for x in refs if x.anlass_id == "1226")
    assert r.name == "73. Niklausschwinget"
    assert r.datum == "2010-12-05"
    assert r.kategorie == "aktiv"
    assert r.ort == "Dietikon ZH"
    assert r.stufe == "regional"
    esaf = next(x for x in refs if x.anlass_id == "999")
    assert esaf.stufe == "eidgenoessisch"
    jung = next(x for x in refs if x.anlass_id == "1452")
    assert jung.kategorie == "jung"
