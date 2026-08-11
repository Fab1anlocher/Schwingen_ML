"""Kader-Aufbau: Porträts + PDF-Teilnehmer zu EINER Schwinger-Liste (§4.2).

Bewusst **zustandslos**: derselbe Input erzeugt immer denselben Kader,
unabhängig davon, was vorher in ``artifacts/raw/schwinger.json`` stand.

Vorher wurde die Datei erst mit den Porträts überschrieben und danach
inkrementell um "Stubs" ergänzt. Das Ergebnis hing damit am (unsichtbaren,
nicht versionierten) Stand des CI-Caches: derselbe Code lieferte an einem Tag
2899 Schwinger und am nächsten 1040 -- ohne dass sich die Quelldaten geändert
hätten. Genau daran ist der tägliche Update-Lauf 20-mal in Folge gescheitert.
"""
from __future__ import annotations

from .identity import Namensindex, baue_namensindex, namens_tokens, stub_id

# Felder, die nur intern beim Porträt-Scrapen anfallen (Bild, Suchstrings, ...).
_INTERNE_FELDER = "portrait_"


def _ohne_interne_felder(profil: dict) -> dict:
    return {k: v for k, v in profil.items() if not k.startswith(_INTERNE_FELDER)}


def namen_aus_gaengen(gaenge: list[dict]) -> set[str]:
    """Alle in den Statistik-PDFs vorkommenden Schwinger-Namen."""
    namen: set[str] = set()
    for g in gaenge:
        for feld in ("schwinger_name", "gegner_name"):
            name = str(g.get(feld) or "").strip()
            if name:
                namen.add(name)
    return namen


def baue_roster(portraits: list[dict], gaenge: list[dict]) -> tuple[list[dict], dict]:
    """Porträts + PDF-Teilnehmer -> vollständige, deduplizierte Schwinger-Liste.

    Rückgabe: ``(eintraege, statistik)``. Ein PDF-Name, der sich über die
    Token-Menge einem Porträt zuordnen lässt, bekommt KEINEN eigenen Eintrag --
    er ist dieselbe Person, nur andersherum geschrieben. Alles andere wird als
    Stub geführt (Gänge zählen, Physis fehlt).
    """
    eintraege = [_ohne_interne_felder(p) for p in portraits]
    index: Namensindex = baue_namensindex(eintraege)
    n_portraits = len(eintraege)

    pdf_namen = namen_aus_gaengen(gaenge)
    zugeordnet = 0
    stubs: dict[str, dict] = {}
    unaufloesbar: list[str] = []

    for name in sorted(pdf_namen):  # sortiert = deterministisch
        if index.finde(name) is not None:
            zugeordnet += 1
            continue
        if namens_tokens(name) in index.mehrdeutig:
            # Mehrere echte Personen dieses Namens (verschiedene Jahrgänge), das
            # PDF nennt aber nur den Namen -- eine Zuordnung wäre geraten. Auch
            # kein Stub: den könnte lade_echte_daten aus demselben Grund nie
            # auflösen, er bliebe ein toter Kadereintrag. Die betroffenen Gänge
            # werden beim Einlesen verworfen und dort gezählt.
            unaufloesbar.append(name)
            continue
        sid = stub_id(name)
        if sid in stubs:
            continue  # gleiche Person, andere Schreibweise -> schon erfasst
        stubs[sid] = {
            "id": sid,
            "name": name,
            "jahrgang": None,
            "kranzstatus": "kein",
            "quellen": ["schlussgang.ch/statistic-pdf"],
        }

    eintraege.extend(stubs[sid] for sid in sorted(stubs))
    statistik = {
        "n_portraits": n_portraits,
        "n_pdf_namen": len(pdf_namen),
        "n_pdf_namen_auf_portraet_gemappt": zugeordnet,
        "n_stubs": len(stubs),
        "n_gesamt": len(eintraege),
        "n_mehrdeutige_namen": len(index.mehrdeutig),
        "mehrdeutige_namen": sorted(" ".join(k) for k in index.mehrdeutig)[:20],
        "n_pdf_namen_unaufloesbar": len(unaufloesbar),
        "pdf_namen_unaufloesbar": sorted(unaufloesbar)[:20],
    }
    return eintraege, statistik


def pruefe_kader(eintraege: list[dict]) -> list[str]:
    """Konsistenzprüfungen auf dem fertigen Kader (für den Datenqualitätsbericht)."""
    probleme: list[str] = []

    ids = [str(e.get("id") or "") for e in eintraege]
    if len(ids) != len(set(ids)):
        doppelt = {i for i in ids if ids.count(i) > 1}
        probleme.append(f"doppelte Schwinger-IDs: {sorted(doppelt)[:5]}")

    nach_tokens: dict[tuple[str, ...], list[str]] = {}
    for e in eintraege:
        nach_tokens.setdefault(namens_tokens(str(e.get("name") or "")), []).append(
            str(e.get("id"))
        )
    gespalten = {k: v for k, v in nach_tokens.items() if len(set(v)) > 1}
    if gespalten:
        beispiele = [f"{' '.join(k)} -> {sorted(set(v))}" for k, v in list(gespalten.items())[:5]]
        probleme.append(
            f"{len(gespalten)} Namen mit mehreren IDs (gespaltene Identität): {beispiele}"
        )
    return probleme
