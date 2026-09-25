"""Export aller Artefakte als JSON (§7, NFR-6).

Alle Artefakte landen sowohl in /artifacts (versioniert im Repo) als auch in
web/public/data (von der Web-App clientseitig geladen).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from . import config
from .config import KLASSEN, MIN_GAENGE_FUER_SICHERHEIT, FORM_FENSTER_K, MERKMAL_VERSION
from .features import FEATURE_NAMES, FEATURE_LABELS
from .modell import TYP_GBM, TYP_LR
from .schema import KRANZSTATUS_ORDINAL, anzeigename, hat_portraet


def _write(pfad: Path, obj, kompakt: bool = False) -> None:
    pfad.parent.mkdir(parents=True, exist_ok=True)
    text = (json.dumps(obj, ensure_ascii=False, separators=(",", ":")) if kompakt
            else json.dumps(obj, ensure_ascii=False, indent=2))
    pfad.write_text(text, encoding="utf-8")


def _dump_beide(name: str, obj, kompakt: bool = False) -> None:
    """Schreibt ein Artefakt nach /artifacts und web/public/data."""
    _write(config.ARTIFACTS_DIR / name, obj, kompakt)
    _write(config.WEB_PUBLIC_DIR / name, obj, kompakt)


# Blattwerte gerundet: spart rund ein Drittel der Dateigrösse; die Abweichung
# zum sklearn-Modell bleibt unter 1e-5 (geprüft in pruefe_modell_export).
# Schwellen bleiben exakt -- eine gerundete Schwelle könnte einen Gang in den
# anderen Ast schicken.
BLATT_STELLEN = 8
MAX_EXPORT_ABWEICHUNG = 1e-5


def _baum_json(knoten) -> list:
    """Ein Baum als Liste, Index = Knotennummer von sklearn.

    Innerer Knoten: [Merkmal, Schwelle, links, rechts] -- links, wenn
    x[Merkmal] <= Schwelle. Blatt: der Wert selbst (Zahl). Fehlende Werte
    gibt es nicht (Merkmale sind nie NaN, s. features._diff_oder_null).
    """
    return [
        round(float(k["value"]), BLATT_STELLEN) if k["is_leaf"]
        else [int(k["feature_idx"]), float(k["num_threshold"]), int(k["left"]), int(k["right"])]
        for k in knoten
    ]


def _stufe_json(sk) -> dict:
    """Eine binäre Boosting-Stufe: Rohwert = basis + Summe der Bäume, dann Sigmoid."""
    return {
        "basis": float(np.ravel(sk._baseline_prediction)[0]),
        "baeume": [_baum_json(iteration[0].nodes) for iteration in sk._predictors],
    }


def modell_json(modell) -> dict:
    """Der modellspezifische Teil von model.json (s. modell.Prognosemodell)."""
    from .modell import spiegel_vektor

    teil = {
        # Mittel/Streuung der Trainingsmerkmale: die LR rechnet damit
        # standardisiert, beide Typen nehmen das Mittel als neutralen Wert
        # der Erklärbalken.
        "standardisierung": {
            "mu": [float(x) for x in modell.mu],
            "sigma": [float(x) for x in modell.sigma],
        },
    }
    if modell.typ == "lr":
        # coef_: (n_klassen, n_features); intercept_: (n_klassen,)
        teil |= {
            "typ": TYP_LR,
            "coef": [[float(v) for v in row] for row in modell.sk.coef_],
            "intercept": [float(v) for v in modell.sk.intercept_],
        }
    else:
        teil |= {
            "typ": TYP_GBM,
            # g = P(Gestellt), s = P(Sieg A | entschieden), je gemittelt mit
            # der gespiegelten Paarung; P = [(1-g)s, g, (1-g)(1-s)], s. modell.py.
            "stufen": {name: _stufe_json(sk) for name, sk in modell.sk.items()},
            # +1 symmetrisches Merkmal, -1 Differenz (Vorzeichen beim Spiegeln).
            "spiegel": [float(v) for v in spiegel_vektor()],
        }
    return teil


def pruefe_modell_export(modell, artefakt: dict, X_probe) -> float:
    """Rechnet das exportierte JSON genau wie die App und vergleicht mit dem
    trainierten Modell. Bricht ab, statt ein abweichendes Modell auszuliefern."""
    from .paritaet import json_inferenz_wie_app

    X_probe = np.asarray(X_probe, dtype=float)[:300]
    if len(X_probe) == 0:
        return 0.0
    p_sk = modell.predict_proba(X_probe)
    abw = max(
        abs(a - b)
        for x, p in zip(X_probe, p_sk)
        for a, b in zip(json_inferenz_wie_app(artefakt, list(x)), p)
    )
    if abw > MAX_EXPORT_ABWEICHUNG:
        raise RuntimeError(f"model.json weicht vom trainierten Modell ab: {abw:.2e}")
    return abw


def exportiere_modell(
    train_res: dict,
    feature_importance: list[dict],
    *,
    elo_streuung: float,
    gestellt_basis: float,
) -> None:
    """model.json für die Inferenz in der App (§7) + feature_importance.json.

    elo_streuung / gestellt_basis: der aktuelle Stand der beiden Grössen, mit
    denen Merkmalsversion 2 rechnet -- die App braucht sie, um den Vektor
    genauso zu bauen wie das Training (s. features.feature_vektor_fuer_prognose).
    """
    modell = train_res["modell"]
    artefakt = {
        "schema_version": config.SCHEMA_VERSION,
        "klassen": KLASSEN,
        "features": FEATURE_NAMES,
        "feature_labels": FEATURE_LABELS,
        **modell_json(modell),
        "config": {
            "min_gaenge_fuer_sicherheit": MIN_GAENGE_FUER_SICHERHEIT,
            "form_fenster_k": FORM_FENSTER_K,
            "elo_start": config.ELO_START,
            "kranzstatus_ordinal": KRANZSTATUS_ORDINAL,
            # Merkmalsdefinition, mit der DIESES Modell trainiert wurde. Die
            # App rechnet danach -- auch dann richtig, wenn dieses model.json
            # dem Code einen Lauf hinterherhinkt (fehlt der Eintrag: Version 1).
            "merkmal_version": MERKMAL_VERSION,
            "elo_streuung": round(float(elo_streuung), 4),
            "gestellt_basis": round(float(gestellt_basis), 6),
        },
        "erstellt": datetime.now(timezone.utc).isoformat(),
    }
    abw = pruefe_modell_export(modell, artefakt, train_res.get("X_test", []))
    print(f"      model.json ({artefakt['typ']}) == trainiertes Modell (max. Abweichung {abw:.1e})", flush=True)
    # Kompakt: die Bäume eingerückt wären ~1 MB statt ~0.3 MB (gzip 120 statt 92 kB).
    _dump_beide("model.json", artefakt, kompakt=True)
    _dump_beide("feature_importance.json", {
        "schema_version": config.SCHEMA_VERSION,
        "klassen": KLASSEN,
        # "koeffizient" (LR: mittlerer Betrag der standardisierten Koeffizienten)
        # oder "permutation" (Boosting: Anstieg des Log-Loss ohne das Merkmal).
        "art": "koeffizient" if modell.typ == "lr" else "permutation",
        "features": feature_importance,
    })


def exportiere_ratings(elo_modell, schwinger: dict) -> None:
    """ratings.json: aktuelles Elo + Gang-Zahl je Schwinger."""
    obj = {
        "schema_version": config.SCHEMA_VERSION,
        "elo_start": config.ELO_START,
        "ratings": {
            sid: {
                "elo": round(elo_modell.get(sid), 1),
                "n_gaenge": elo_modell.gaenge_gezaehlt.get(sid, 0),
            }
            for sid in schwinger
        },
    }
    _dump_beide("ratings.json", obj)


def exportiere_schwinger(
    schwinger: dict,
    form_aktuell: dict,
    ueberraschung: dict | None = None,
    anzahl_feste: dict | None = None,
    aktive: set | None = None,
    gestellt_neigung: dict | None = None,
    teilverband_geschaetzt: dict | None = None,
    ranglisten: dict | None = None,
) -> None:
    """schwinger.json: Profil + aktuelle Form (für Live-Prognose & Suche FR-5).

    gestellt_neigung: geschrumpfte Gestellt-Quote je Schwinger (Merkmals-
    version 2, s. features.gestellt_neigung_aktuell). Fehlt sie (null), rechnet
    die App mit dem Durchschnitt -- neutral, wie für einen Neuling.

    teilverband_geschaetzt: nur für Schwinger ohne Porträt-Verband, aus ihren
    Festen geschätzt (s. verbandsschaetzung.py). Eigenes Feld, damit gemessen
    und geschätzt nie verwechselt werden; das Modell nutzt nur ``teilverband``.

    ranglisten: aus den offiziellen Schlussranglisten (s. ranglisten.py) --
    ``kraenze`` je Schwinger, ``klubs``, ``senne_turner`` und ``verband_klub``
    (Teilverband + Gauverband über den Klub, nur ohne Porträt-Verband).
    Ohne Ranglisten (synthetische Daten) bleiben die Felder null.

    Sensible Felder werden NICHT exportiert (NFR-5): kein Geburtsdatum, nur
    Jahrgang bleibt intern; Anzeige nutzt Alter.
    """
    ueberraschung = ueberraschung or {}
    anzahl_feste = anzahl_feste or {}
    aktive = aktive if aktive is not None else set()
    gestellt_neigung = gestellt_neigung or {}
    teilverband_geschaetzt = teilverband_geschaetzt or {}
    rl = ranglisten or {}
    kraenze = rl.get("kraenze")
    klubs = rl.get("klubs") or {}
    senne_turner = rl.get("senne_turner") or {}
    verband_klub = rl.get("verband_klub") or {}
    kranzstatus_rl = rl.get("kranzstatus") or {}
    festsiege = rl.get("festsiege")
    liste = []
    for sid, s in schwinger.items():
        u = ueberraschung.get(sid)
        groesster_erfolg = None
        if u and u.get("groesster_erfolg"):
            ge = u["groesster_erfolg"]
            gegner = schwinger.get(ge["gegner_id"])
            groesster_erfolg = {
                "gegner_name": anzeigename(gegner) if gegner else ge["gegner_id"],
                "event_id": ge["event_id"],
                "datum": ge["datum"],
                "eigenes_elo": ge["eigenes_elo"],
                "gegner_elo": ge["gegner_elo"],
            }
        liste.append({
            "id": sid,
            "name": anzeigename(s),
            "jahrgang": s.jahrgang,
            "groesse_cm": s.groesse_cm,
            "gewicht_kg": s.gewicht_kg,
            "kranzstatus": s.kranzstatus,
            # Nur ohne Porträt: Kranzstatus laut Sternen der Rangliste (Anzeige).
            # Das Modell nutzt weiter nur ``kranzstatus`` aus dem Porträt.
            "kranzstatus_rangliste": (
                kranzstatus_rl.get(sid) if not hat_portraet(s.quellen) else None
            ),
            "teilverband": s.teilverband,
            # Über den Schwingklub (Mitgliedschaft, gemessen) -- vor der
            # Schätzung aus Festbesuchen, die nur noch einspringt, wo der Klub
            # unbekannt ist.
            "teilverband_klub": None if s.teilverband else (verband_klub.get(sid) or (None, None))[0],
            "kanton_klub": None if s.kanton else (verband_klub.get(sid) or (None, None))[1],
            "teilverband_geschaetzt": (
                None if s.teilverband or sid in verband_klub else teilverband_geschaetzt.get(sid)
            ),
            "kanton": s.kanton,
            "schwingklub": s.schwingklub or klubs.get(sid),
            "senne_turner": s.senne_turner or senne_turner.get(sid),
            # Gewonnene Kränze seit Datenbeginn laut offizieller Schlussrangliste;
            # null = keine Ranglisten geladen (nicht: null Kränze).
            "kraenze": (kraenze.get(sid, {}).get("gesamt", 0) if kraenze is not None else None),
            "kraenze_nach_typ": (kraenze.get(sid, {}).get("nach_typ", {}) if kraenze is not None else None),
            "bevorzugte_schwuenge": s.bevorzugte_schwuenge,
            "form": round(form_aktuell.get(sid, 0.5), 3),
            "gestellt_neigung": (
                round(gestellt_neigung[sid], 5) if sid in gestellt_neigung else None
            ),
            "ueberraschungsindex": u["index"] if u else None,
            "n_bewertete_gaenge": u["n"] if u else 0,
            "anzahl_feste": anzahl_feste.get(sid, 0),
            "aktiv": sid in aktive,
            "groesster_erfolg": groesster_erfolg,
            # Festsiege seit Datenbeginn (Rang 1 der Schlussrangliste, jüngster
            # zuerst); null = keine Ranglisten geladen.
            "festsiege": (festsiege.get(sid, []) if festsiege is not None else None),
            # Von einem gleichnamigen Porträt-Schwinger getrennt (namensvettern.py).
            "namensvetter_von": s.namensvetter_von,
            "quellen": s.quellen,
        })
    liste.sort(key=lambda x: x["name"])
    _dump_beide("schwinger.json", {
        "schema_version": config.SCHEMA_VERSION,
        "schwinger": liste,
    })


def exportiere_events(events: list, kommende: list | None = None, *,
                      ueberblick: dict | None = None, schwinger: dict | None = None) -> None:
    """events.json: vergangene Feste + kommende Feste/Paarungen (FR-2).

    ``ueberblick`` (aus den Schlussranglisten, s. ranglisten.fest_ueberblick)
    ergänzt jedes vergangene Fest um Sieger, Teilnehmer und Kränze -- für den
    Rückblick auf der Feste-Seite. Ohne Ranglisten fehlen die Felder.
    """
    ueberblick = ueberblick or {}
    schwinger = schwinger or {}
    vergangene = []
    for e in events:
        d = e.to_dict()
        u = ueberblick.get(e.id)
        if u:
            d["sieger"] = [{"id": sid, "name": anzeigename(schwinger[sid]) if sid in schwinger else sid}
                           for sid in u["sieger"]]
            d["n_teilnehmer"] = u["n_teilnehmer"]
            d["n_kraenze"] = u["n_kraenze"]
        vergangene.append(d)
    _dump_beide("events.json", {
        "schema_version": config.SCHEMA_VERSION,
        "vergangene": vergangene,
        "kommende": kommende or [],
    })


_ERGEBNIS_CODE = {"sieg_a": "A", "gestellt": "D", "sieg_b": "B"}


def _leerer_eintrag() -> dict:
    return {
        "n_schwinger": 0, "elo_summe": 0.0, "n_top": 0,
        "n_kranzer": 0, "n_eidgenosse": 0, "n_koenig": 0,
        "n_siege": 0, "n_gestellt": 0, "n_niederlagen": 0,
    }


def _eintrag_zu_dict(name: str, e: dict) -> dict:
    # Zähl-Felder auf ganze Zahlen runden: bei aufgeteilten Mehr-Kantons-
    # Verbänden (s. exportiere_kantone) sind sie Bruchzahlen; für die Anzeige
    # sollen es Anzahlen bleiben. Ø-Elo aus den ungerundeten Summen.
    return {
        "kanton": name,
        "n_schwinger": round(e["n_schwinger"]),
        "elo_avg": round(e["elo_summe"] / e["n_schwinger"], 1) if e["n_schwinger"] else None,
        "n_top_schwinger": round(e["n_top"]),
        "n_kranzer": round(e["n_kranzer"]),
        "n_eidgenosse": round(e["n_eidgenosse"]),
        "n_koenig": round(e["n_koenig"]),
        "n_siege": round(e["n_siege"]),
        "n_gestellt": round(e["n_gestellt"]),
        "n_niederlagen": round(e["n_niederlagen"]),
    }


def _gauverband_stats(schwinger: dict, elo_modell, gaenge: list,
                      ranglisten: dict | None = None) -> tuple[dict[str, dict], float]:
    """Rohe Statistik je Kantonal-/Gauverband (29 Verbände).

    Ein Wurf pro Schwinger in GENAU einen Verband — anders als die daraus
    abgeleiteten politischen Kantone (mehrere Verbände wie Bern: Oberland/
    Emmental/... fallen dort zusammen, s. exportiere_kantone).

    Verband: aus dem Porträt, sonst über den Schwingklub der Schlussrangliste
    (``ranglisten["verband_klub"]``). Früher nur Porträts -- das waren 24 %
    des Kaders, fast nur die Erfolgreicheren. Kranzstatus ohne Porträt aus der
    Rangliste. Gezählt wird nur, wer mindestens MIN_GAENGE_FUER_SICHERHEIT
    Gänge hat: ein Elo nach ein, zwei Gängen ist kaum vom Startwert weg und
    zöge den Kantonsschnitt Richtung 1500, je mehr Nachwuchs ein Kanton hat.
    """
    rl = ranglisten or {}
    verband_klub = rl.get("verband_klub") or {}
    kranzstatus_rl = rl.get("kranzstatus") or {}
    n_gaenge: dict[str, int] = {}
    for g in gaenge:
        for sid in (g.schwinger_a_id, g.schwinger_b_id):
            n_gaenge[sid] = n_gaenge.get(sid, 0) + 1

    def verband_von(sid: str, s) -> str | None:
        return s.kanton or (verband_klub.get(sid) or (None, None))[1]

    gezaehlt = {sid: s for sid, s in schwinger.items()
                if n_gaenge.get(sid, 0) >= MIN_GAENGE_FUER_SICHERHEIT and verband_von(sid, s)}
    elos = [elo_modell.get(sid) for sid in gezaehlt]
    schwelle_top = float(np.percentile(elos, 90)) if len(elos) >= 10 else max(elos, default=0.0)

    verbaende: dict[str, dict] = {}
    sid_zu_verband: dict[str, str] = {}

    for sid, s in gezaehlt.items():
        verband = verband_von(sid, s)
        sid_zu_verband[sid] = verband
        e = verbaende.setdefault(verband, _leerer_eintrag())
        elo = elo_modell.get(sid)
        e["n_schwinger"] += 1
        e["elo_summe"] += elo
        if elo >= schwelle_top:
            e["n_top"] += 1
        status = s.kranzstatus if hat_portraet(s.quellen) else kranzstatus_rl.get(sid, "kein")
        if status == "kranzer":
            e["n_kranzer"] += 1
        elif status == "eidgenosse":
            e["n_eidgenosse"] += 1
        elif status == "koenig":
            e["n_koenig"] += 1

    for g in gaenge:
        for sid, ist_a in ((g.schwinger_a_id, True), (g.schwinger_b_id, False)):
            verband = sid_zu_verband.get(sid)
            if verband is None:
                continue
            e = verbaende[verband]
            if g.ergebnis == "gestellt":
                e["n_gestellt"] += 1
            elif (g.ergebnis == "sieg_a") == ist_a:
                e["n_siege"] += 1
            else:
                e["n_niederlagen"] += 1

    return verbaende, schwelle_top


def exportiere_kantone(schwinger: dict, elo_modell, gaenge: list, *,
                       ranglisten: dict | None = None) -> None:
    """kantone.json + gauverbaende.json: Statistik für Schweiz-Karte & Detailansicht.

    Beide werden aus derselben Kantonal-/Gauverband-Aggregation abgeleitet
    (pipeline/kantone.py): kantone.json summiert Verbände auf den politischen
    Kanton (für die Karte, z.B. Bern: alle 6 Regionalverbände zusammen);
    gauverbaende.json behält die 29 Verbände einzeln (z.B. für eine Bern-
    interne Detailansicht ohne Kartenverzerrung, da echte Gauverband-Grenzen
    nicht dem politischen Kanton entsprechen und nicht als Karte verfügbar sind).
    """
    from .kantone import kantone_fuer

    verbaende, schwelle_top = _gauverband_stats(schwinger, elo_modell, gaenge, ranglisten)

    kantone: dict[str, dict] = {}
    for verband_name, e in verbaende.items():
        ziel_kantone = kantone_fuer(verband_name)
        if not ziel_kantone:
            continue
        # Verbände über mehrere Kantone (Appenzell -> AR+AI, Ob-/Nidwalden)
        # werden GLEICHMÄSSIG aufgeteilt statt in jeden Kanton voll dupliziert.
        # Sonst zählt ein Appenzeller Schwinger doppelt (in AR und AI) und die
        # Kantons-Summe (767) läge über der echten Schwingerzahl (708). Der
        # Ø-Elo bleibt exakt (Summe und Anzahl durch denselben Teiler geteilt).
        teiler = len(ziel_kantone)
        for kanton in ziel_kantone:
            k = kantone.setdefault(kanton, _leerer_eintrag())
            for feld in k:
                k[feld] += e[feld] / teiler

    kantone_liste = sorted((_eintrag_zu_dict(n, e) for n, e in kantone.items()), key=lambda x: x["kanton"])
    _dump_beide("kantone.json", {
        "schema_version": config.SCHEMA_VERSION,
        "top_schwelle_elo": round(schwelle_top, 1),
        "min_gaenge": MIN_GAENGE_FUER_SICHERHEIT,
        "kantone": kantone_liste,
    })

    gauverband_liste = sorted((_eintrag_zu_dict(n, e) for n, e in verbaende.items()), key=lambda x: x["kanton"])
    _dump_beide("gauverbaende.json", {
        "schema_version": config.SCHEMA_VERSION,
        "top_schwelle_elo": round(schwelle_top, 1),
        "gauverbaende": gauverband_liste,
    })


def exportiere_kopf_an_kopf(gaenge: list) -> None:
    """Kompakter Kopf-an-Kopf-Index je Paar (schwinger_a_id < schwinger_b_id).

    Bewusst NICHT in web/public/data (clientseitig geladen): bei 100k+ Gängen
    wäre das ein zu grosser Download für eine Detail-Ansicht, die pro Aufruf
    nur EIN Paar braucht. Wird stattdessen serverseitig von einer Next.js-
    Route gelesen (web/app/api/kopf-an-kopf), die nur das angefragte Paar
    zurückgibt.

    Da diese Datei (anders als artifacts/raw/) für den Vercel-Build committed
    sein muss, ist die Kodierung bewusst knapp gehalten: numerischer Index
    statt voller Schwinger-IDs als Paar-Schlüssel, 1-Buchstabe-Ergebniscode,
    Datum/Fest-Typ nicht dupliziert (Client kennt sie schon aus events.json).
    Ohne das wäre die Datei >19 MB und würde bei jedem täglichen Cron-Commit
    unbegrenzt weiterwachsen (§NFR-1 täglicher Lauf).
    """
    index: dict[str, int] = {}
    event_index: dict[str, int] = {}

    def _idx(sid: str, register: dict[str, int]) -> int:
        if sid not in register:
            register[sid] = len(register)
        return register[sid]

    paare: dict[str, list] = {}
    for g in gaenge:
        key = f"{_idx(g.schwinger_a_id, index)}_{_idx(g.schwinger_b_id, index)}"
        paare.setdefault(key, []).append(
            [_idx(g.event_id, event_index), _ERGEBNIS_CODE[g.ergebnis]]
        )
    obj = {
        "schema_version": config.SCHEMA_VERSION,
        "index": index,
        "event_index": event_index,
        "paare": paare,
    }
    _write(config.ARTIFACTS_DIR / "kopf_an_kopf.json", obj)
    _write(config.WEB_SERVER_DATA_DIR / "kopf_an_kopf.json", obj)


def exportiere_cluster(cluster_res: dict | None) -> None:
    """cluster.json: Schwingertypen (K-Means über Physis+Stil, s. pipeline/clustering.py).

    None wenn zu wenig Schwinger mit Profildaten (z.B. synthetische Demodaten) --
    dann bleibt eine evtl. vorher exportierte Datei unangetastet (kein Überschreiben
    mit leerem/irreführendem Zustand, gleiche Konvention wie exportiere_benchmark).
    """
    if cluster_res is None:
        return
    _dump_beide("cluster.json", {
        "schema_version": config.SCHEMA_VERSION,
        **cluster_res,
    })


_KANDIDAT_LABELS = {
    "kranz_heuristik": "Kranz-Heuristik",
    "elo_baseline": "Elo-Baseline",
    "ml_ohne_elo": "ML ohne Elo/Historie",
    "lr_komplett": "Logistic Regression (bis 25.09.2026)",
    "ml_komplett": "Gradient Boosting (Produktionsmodell)",
}


def exportiere_benchmark(benchmark_res: dict) -> None:
    """benchmark.json: 4-Wege-Vergleich Heuristik/Elo/ML-ohne-Elo/ML-komplett.

    Siehe pipeline/benchmark.py für Methodik (identischer Holdout, nur echte
    -- nicht augmentierte -- Testgänge, Accuracy + multiklassiger Brier-Score
    + MAE/MSE auf dem Punktwert des Gangs).
    """
    kandidaten = [
        {
            "key": key,
            "label": _KANDIDAT_LABELS.get(key, key),
            "accuracy": werte["accuracy"],
            "brier_score": werte["brier_score"],
            "mae": werte["mae"],
            "mse": werte["mse"],
        }
        for key, werte in benchmark_res["kandidaten"].items()
    ]
    _dump_beide("benchmark.json", {
        "schema_version": config.SCHEMA_VERSION,
        "holdout_jahr": benchmark_res["holdout_jahr"],
        "n_test": benchmark_res["n_test"],
        "kandidaten": kandidaten,
    })


def _nur_portraet_block(modell: dict | None, baseline: dict | None) -> dict:
    if not modell or not modell.get("n"):
        return {"n": 0}
    block = {"modell": modell}
    if baseline and baseline.get("n"):
        block["baseline_elo"] = {
            "n": baseline["n"],
            "log_loss": round(baseline["log_loss"], 4),
            "accuracy": round(baseline["accuracy"], 4),
        }
    return block


# --- Verlauf der Modellgüte (Roadmap T1) ---------------------------------
# Jeder Lauf überschrieb bisher report.json; ob das Modell über Wochen
# schlechter wurde, sah niemand. Jetzt hängt jeder Lauf eine Zeile an:
# eine je Tag und Modellstand (Typ + Merkmalsversion). Ein Modellwechsel am
# selben Tag behält so den Punkt davor -- der Sprung bleibt sichtbar.
VERLAUF_MAX_EINTRAEGE = 730
# Warnen, wenn der Log-Loss so viel über dem Median der letzten Läufe liegt
# (nur Läufe mit gleichem Holdout-Jahr, Modelltyp und Merkmalsversion --
# ein Modellwechsel oder eine neue Saison ist kein Rückschritt).
VERLAUF_WARN_ANSTIEG = 0.01
VERLAUF_VERGLEICH_LAEUFE = 14


def verlauf_eintrag(report: dict) -> dict:
    """Die Kennzahlen eines report.json, die im Verlauf stehen."""
    kal = report.get("gestellt_kalibrierung") or {}
    base = report.get("baseline_elo") or {}
    return {
        "datum": str(report.get("erstellt", ""))[:10],
        "modell_typ": report.get("modell_typ", "lr"),
        "merkmal_version": report.get("merkmal_version", 1),
        "holdout_jahr": report.get("holdout_jahr"),
        "log_loss": report["modell"]["log_loss"],
        "accuracy": report["modell"]["accuracy"],
        "baseline_log_loss": base.get("log_loss"),
        "gestellt_vorhergesagt": kal.get("vorhergesagt"),
        "gestellt_eingetreten": kal.get("eingetreten"),
        "auc_gestellt": kal.get("auc"),
        "n_gaenge": (report.get("datenbasis") or {}).get("n_gaenge"),
        "n_test": report.get("n_test"),
    }


def verlauf_warnung(laeufe: list[dict]) -> str | None:
    """Warntext, wenn der jüngste Lauf deutlich schlechter ist als die davor."""
    if len(laeufe) < 2:
        return None
    jetzt = laeufe[-1]
    vergleich = [
        l["log_loss"] for l in laeufe[:-1]
        if (l["holdout_jahr"], l["modell_typ"], l["merkmal_version"])
        == (jetzt["holdout_jahr"], jetzt["modell_typ"], jetzt["merkmal_version"])
    ][-VERLAUF_VERGLEICH_LAEUFE:]
    if len(vergleich) < 3:
        return None
    median = float(np.median(vergleich))
    if jetzt["log_loss"] > median + VERLAUF_WARN_ANSTIEG:
        return (f"Log-Loss {jetzt['log_loss']:.4f} liegt {jetzt['log_loss'] - median:+.4f} über dem "
                f"Median der letzten {len(vergleich)} vergleichbaren Läufe ({median:.4f})")
    return None


def verlauf_schluessel(eintrag: dict) -> tuple:
    """Ein Eintrag je Tag und Modellstand; bei gleichem Schlüssel zählt der jüngste Lauf."""
    return eintrag.get("datum"), eintrag.get("modell_typ"), eintrag.get("merkmal_version")


def ergaenze_verlauf(report: dict) -> dict:
    """report_verlauf.json fortschreiben (s. verlauf_schluessel)."""
    pfad = config.ARTIFACTS_DIR / "report_verlauf.json"
    laeufe = []
    if pfad.exists():
        try:
            laeufe = json.loads(pfad.read_text(encoding="utf-8")).get("laeufe", [])
        except (OSError, ValueError):
            laeufe = []
    eintrag = verlauf_eintrag(report)
    laeufe = [l for l in laeufe if verlauf_schluessel(l) != verlauf_schluessel(eintrag)] + [eintrag]
    # sorted ist stabil: am selben Tag bleibt die Reihenfolge der Läufe erhalten.
    laeufe = sorted(laeufe, key=lambda l: l["datum"])[-VERLAUF_MAX_EINTRAEGE:]
    _dump_beide("report_verlauf.json", {"schema_version": config.SCHEMA_VERSION, "laeufe": laeufe})
    return {"n_laeufe": len(laeufe), "warnung": verlauf_warnung(laeufe)}


def exportiere_report(train_res: dict, baseline: dict, warnungen: list[str],
                      n_gaenge: int, n_schwinger: int,
                      datenqualitaet: dict | None = None,
                      baseline_portraet: dict | None = None) -> dict:
    """report.json: Trainingslauf-Bericht (ML-6, reproduzierbar, versioniert)."""
    ll = train_res["log_loss"]
    base_ll = baseline["log_loss"]
    acc = train_res["accuracy"]
    base_acc = baseline["accuracy"]
    erreicht_log_loss = bool(ll < base_ll)
    erreicht_accuracy = bool(acc >= base_acc)
    obj = {
        "schema_version": config.SCHEMA_VERSION,
        "erstellt": datetime.now(timezone.utc).isoformat(),
        "lauf_id": datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "seed": config.SEED,
        "datenbasis": {"n_gaenge": n_gaenge, "n_schwinger": n_schwinger},
        "holdout_jahr": train_res["holdout_jahr"],
        # "gbm" (zweistufiges Gradient Boosting) oder "lr" (Logistic
        # Regression), s. modell.py; n_baeume je Stufe, bei der LR null.
        "modell_typ": train_res.get("modell_typ", "lr"),
        "n_baeume": train_res.get("n_baeume"),
        "n_train": train_res["n_train"],
        "n_test": train_res["n_test"],
        "modell": {
            "log_loss": round(ll, 4),
            "accuracy": round(train_res["accuracy"], 4),
            # MAE/MSE auf dem Punktwert des Gangs (Sieg=1/Gestellt=0.5/
            # Niederlage=0), s. pipeline/metriken.py.
            "mae": round(train_res["mae"], 4),
            "mse": round(train_res["mse"], 4),
        },
        "baseline_elo": {
            "log_loss": round(base_ll, 4),
            "accuracy": round(base_acc, 4),
        },
        "schlaegt_baseline": erreicht_log_loss,
        "accuracy_gg_baseline": round(acc - base_acc, 4),
        "verbesserung_log_loss": round(base_ll - ll, 4),
        "klassen": KLASSEN,
        "konfusionsmatrix": train_res.get("confusion_matrix"),
        # Getrennte Auswertung nur auf Porträt-gegen-Porträt-Gängen (s.
        # train._bewerte_nur_portraet) -- mit der Elo-Baseline auf denselben
        # Gängen, damit auch dieser Vergleich auf identischer Menge läuft.
        "nur_portraet": _nur_portraet_block(train_res.get("nur_portraet"), baseline_portraet),
        # Kalibrierung der Gestellt-Klasse (s. metriken.gestellt_kalibrierung):
        # die einzige Klasse, die fast nie die wahrscheinlichste ist -- Accuracy
        # und Log-Loss allein zeigen nicht, ob P(gestellt) stimmt.
        "gestellt_kalibrierung": train_res.get("kalibrierung"),
        "merkmal_version": MERKMAL_VERSION,
        "training_ab": train_res.get("training_ab"),
        "erfolgskriterien": {
            "log_loss_besser_als_baseline": erreicht_log_loss,
            "accuracy_mindestens_baseline": erreicht_accuracy,
            "gesamt_erfuellt": bool(erreicht_log_loss and erreicht_accuracy),
        },
        "parsing_warnungen": warnungen[:50],
        "n_parsing_warnungen": len(warnungen),
        "datenqualitaet": datenqualitaet or {},
    }
    # Verlauf zuerst fortschreiben: seine Warnung gehört in denselben Bericht.
    obj["modell_verlauf"] = ergaenze_verlauf(obj)
    _dump_beide("report.json", obj)
    return obj
