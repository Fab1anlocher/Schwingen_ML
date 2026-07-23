"""Tests für die Schwingertyp-Clusterung (K-Means über Physis+Stil)."""
from __future__ import annotations

from pipeline.clustering import K_BEREICH, berechne_cluster
from pipeline.schema import Schwinger


def _sw(sid: str, gewicht: float | None, groesse: float | None, schwuenge=None) -> Schwinger:
    return Schwinger(
        id=sid, name=sid, gewicht_kg=gewicht, groesse_cm=groesse,
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
        f"leicht{i}": _sw(f"leicht{i}", 70.0 + i * 0.7, 165.0 + i * 0.6, ["Kurz"])
        for i in range(20)
    }
    schwer = {
        f"schwer{i}": _sw(f"schwer{i}", 130.0 + i * 0.7, 195.0 + i * 0.6, ["Brienzer"])
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
