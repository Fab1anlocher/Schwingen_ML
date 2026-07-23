"""Tests für die Schwingertyp-Clusterung (K-Means über Physis+Stil)."""
from __future__ import annotations

from pipeline.clustering import K_BEREICH, N_AEHNLICHSTE, N_VERTRETER, berechne_cluster
from pipeline.schema import Schwinger


def _sw(
    sid: str, gewicht: float | None, groesse: float | None, schwuenge=None, teilverband=None
) -> Schwinger:
    return Schwinger(
        id=sid, name=sid, gewicht_kg=gewicht, groesse_cm=groesse, teilverband=teilverband,
        bevorzugte_schwuenge=schwuenge or [], quellen=["schlussgang.ch"],
    )


def test_zu_wenig_profildaten_gibt_none():
    # Unter der Mindestschwelle (3 * K_BEREICH.stop) -> kein sinnvolles Clustering.
    schwinger = {f"s{i}": _sw(f"s{i}", 90.0, 180.0) for i in range(3 * K_BEREICH.stop - 1)}
    assert berechne_cluster(schwinger) is None


def test_ohne_gewicht_oder_groesse_zaehlt_nicht_als_kandidat():
    schwinger = {
        "a": _sw("a", None, 180.0),
        "b": _sw("b", 90.0, None),
        **{f"s{i}": _sw(f"s{i}", 80.0 + i, 170.0 + i) for i in range(3 * K_BEREICH.stop)},
    }
    ergebnis = berechne_cluster(schwinger)
    ids = {p["schwinger_id"] for p in ergebnis["punkte"]}
    assert "a" not in ids and "b" not in ids


def test_zwei_klar_getrennte_gruppen_werden_sinnvoll_gruppiert():
    # Leichte/kleine vs. schwere/grosse Gruppe, klar separiert -> gute Struktur erwartet.
    # Kontinuierliche Streuung innerhalb jeder Gruppe (statt weniger Duplikate),
    # sonst bevorzugt der Silhouette-Score kuenstlich viele Mikro-Cluster aus
    # exakt gleichen Punkten statt der zwei echten, breiteren Gruppen.
    leicht = {
        f"leicht{i}": _sw(
            f"leicht{i}", 70.0 + i * 0.7, 165.0 + i * 0.6, ["Kurz"], teilverband="berner"
        )
        for i in range(20)
    }
    schwer = {
        f"schwer{i}": _sw(
            f"schwer{i}", 130.0 + i * 0.7, 195.0 + i * 0.6, ["Brienzer"], teilverband="innerschweizer"
        )
        for i in range(20)
    }
    schwinger = {**leicht, **schwer}

    ergebnis = berechne_cluster(schwinger)

    assert ergebnis is not None
    assert ergebnis["k"] in K_BEREICH
    assert -1.0 <= ergebnis["silhouette"] <= 1.0
    assert ergebnis["silhouette"] > 0.3  # klar getrennte Gruppen -> deutliche Struktur
    assert len(ergebnis["punkte"]) == len(schwinger)
    assert {p["schwinger_id"] for p in ergebnis["punkte"]} == set(schwinger.keys())

    # K_BEREICH startet bei 3 (mindestens 3 Typen), daher kann eine der beiden
    # echten Gruppen in Untergruppen zerfallen -- aber "leicht" und "schwer"
    # duerfen NIE denselben Cluster teilen, dafuer sind sie zu weit auseinander.
    by_id = {p["schwinger_id"]: p["cluster"] for p in ergebnis["punkte"]}
    leicht_cluster = {by_id[sid] for sid in leicht}
    schwer_cluster = {by_id[sid] for sid in schwer}
    assert leicht_cluster.isdisjoint(schwer_cluster)

    summe_n = sum(c["n"] for c in ergebnis["cluster_zusammenfassung"])
    assert summe_n == len(schwinger)

    # KNN-Ähnlichkeit (ersetzt die alte Hand-Heuristik): jeder "leicht*"
    # sollte nur andere "leicht*" als Top-Treffer bekommen, nie "schwer*" --
    # die Gruppen sind dafür weit genug auseinander.
    aehnlichste = ergebnis["aehnlichste"]
    assert set(aehnlichste.keys()) == set(schwinger.keys())
    for sid in leicht:
        treffer = aehnlichste[sid]
        assert 1 <= len(treffer) <= N_AEHNLICHSTE
        assert all(t["schwinger_id"] in leicht for t in treffer)
        assert all(t["schwinger_id"] != sid for t in treffer)  # nie sich selbst
        assert all(0.0 < t["score"] <= 1.0 for t in treffer)
        # Absteigend nach Ähnlichkeit sortiert (naechster Nachbar zuerst).
        scores = [t["score"] for t in treffer]
        assert scores == sorted(scores, reverse=True)

    # Interpretierbarkeit: jeder Cluster bekommt typische Vertreter, eine
    # Auszeichnung und (nur "schwer", da einheitlich "innerschweizer") einen
    # erkannten Teilverband-Schwerpunkt.
    assert ergebnis["merkmale"][:3] == ["gewicht_kg", "groesse_cm", "kompaktheit"]
    for c in ergebnis["cluster_zusammenfassung"]:
        assert 1 <= len(c["typische_vertreter"]) <= N_VERTRETER
        assert set(c["typische_vertreter"]).issubset(schwinger.keys())
        assert isinstance(c["auszeichnung"], str) and c["auszeichnung"]
        assert isinstance(c["kompaktheit_avg"], float)
        if set(c["typische_vertreter"]) & set(schwer.keys()):
            assert c["teilverband_schwerpunkt"] == "innerschweizer"


def test_schwungnamen_werden_gross_kleinschreibung_normalisiert():
    # Rohdaten schreiben denselben Schwung uneinheitlich ("innerer Haken" /
    # "Innerer Haken") -- ohne Normalisierung wuerden das zwei Spalten,
    # jede unter der Haeufigkeitsschwelle, obwohl zusammen weit drüber.
    a = {f"a{i}": _sw(f"a{i}", 90.0 + i, 180.0 + i, ["innerer Haken"]) for i in range(6)}
    b = {f"b{i}": _sw(f"b{i}", 90.0 + i, 180.0 + i, ["Innerer Haken"]) for i in range(6)}
    fuellung = {f"f{i}": _sw(f"f{i}", 90.0 + i, 180.0 + i) for i in range(3 * K_BEREICH.stop)}
    schwinger = {**a, **b, **fuellung}

    ergebnis = berechne_cluster(schwinger)

    assert ergebnis is not None
    assert "innerer Haken" in ergebnis["merkmale"]
    assert "Innerer Haken" not in ergebnis["merkmale"]


def test_kompaktheit_ist_gewicht_pro_groesse_quadrat():
    # Gewicht/Groesse variieren leicht (sonst identische Punkte -> Clustering
    # entartet, s. andere Tests), aber im GLEICHEN Verhaeltnis (Faktor 2 in
    # Groesse-Metern zum Quadrat) -- Kompaktheit bleibt dadurch exakt 25.0 fuer alle.
    schwinger = {
        f"s{i}": _sw(f"s{i}", 100.0 + i, (2.0 * ((100.0 + i) / 100.0) ** 0.5) * 100.0)
        for i in range(3 * K_BEREICH.stop)
    }
    ergebnis = berechne_cluster(schwinger)
    assert ergebnis is not None
    for c in ergebnis["cluster_zusammenfassung"]:
        assert abs(c["kompaktheit_avg"] - 25.0) < 0.01
