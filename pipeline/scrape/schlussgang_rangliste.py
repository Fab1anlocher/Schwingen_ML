"""Parser für die Schlussranglisten von schlussgang.ch (offizielle ESV-Ranglisten).

    JSON:API: node/event -> field_final_ranking_pdf (file--file) -> uri.url
    meist:    /sites/default/files/event-ranking-list/<nid>-final.pdf

Die Fusszeile nennt "Quelle: ESV": das ist die offizielle Rangliste des
Eidgenössischen Schwingerverbands, von schlussgang.ch veröffentlicht. esv.ch
selbst sperrt Rechenzentrums-IPs (auch GitHub-Runner) per Firewall, schon
robots.txt antwortet 403 -- über schlussgang.ch kommt dieselbe Liste auf
erlaubtem Weg.

Anders als die Statistik-PDF (nur Namen und Gänge) steht hier JEDER
Teilnehmer mit Wohnort, Schwingklub, Senn/Turner, Kranzabzeichen (Sterne) und
dem Status an diesem Fest ("Kranz", "Neukranzer", "Neueidgenosse").

Layout (vermessen an 13 Ranglisten 2024-2026, alle Festarten): eine Kopfzeile
"Rang Punkte Resultat Name Vorname Wohnort Schwingklub Status", deren
x-Positionen je PDF leicht verschieben -- darum werden die Spaltengrenzen je
Seite aus der Kopfzeile gelesen statt fest verdrahtet. Wohnort und Klub lassen
sich nur über die Spalte trennen ("Röthenbach im Emmental" + "Siehen").

Der Status steht nicht immer auf der Zeile: "Neueidgenosse" sitzt am
Eidgenössischen ein paar Punkte tiefer und weiter links als die Kopfzeile.
Er wird darum über sein Vokabular erkannt und einer Statuszeile ohne eigene
Daten der Rangzeile darüber zugeordnet.
"""
from __future__ import annotations

import io
import re
from collections import defaultdict

_RANG_RE = re.compile(r"^\d{1,3}[a-z]?$")
_PUNKTE_RE = re.compile(r"^(\d{1,2}\.\d{2})(.*)$")   # manche PDFs kleben das Resultat an
_RESULTAT_RE = re.compile(r"^[+\-o0]{1,10}$")
_STERNE_RE = re.compile(r"^\*{1,3}$")
_STERN_SUFFIX_RE = re.compile(r"^(.+?)(\*{1,3})$")
STATUS_WOERTER = ("Kranz", "Neukranzer", "Neueidgenosse")
_SENNE_TURNER = {"S": "senne", "T": "turner"}
_KOPF = ("Wohnort", "Schwingklub")
# Toleranzen in PDF-Punkten.
_ZEILEN_TOLERANZ = 2.5
_SPALTEN_TOLERANZ = 3.0
_STATUSZEILE_ABSTAND = 8.0


class RanglisteUnlesbar(ValueError):
    """Kein erkennbares Ranglisten-Layout (z.B. Fremdformat eines Verbands)."""


def _zeilen(woerter: list[dict]) -> list[list[dict]]:
    """Wörter zu Zeilen gruppieren (nach 'top'), jede Zeile nach x sortiert."""
    zeilen: list[list[dict]] = []
    for w in sorted(woerter, key=lambda w: (w["top"], w["x0"])):
        if zeilen and abs(zeilen[-1][0]["top"] - w["top"]) <= _ZEILEN_TOLERANZ:
            zeilen[-1].append(w)
        else:
            zeilen.append([w])
    return [sorted(z, key=lambda w: w["x0"]) for z in zeilen]


def _spalten(woerter: list[dict]) -> dict[str, float] | None:
    """x-Positionen aus der Kopfzeile dieser Seite; None ohne Kopfzeile."""
    pos = {}
    for w in woerter:
        if w["text"] in (*_KOPF, "Status") and w["text"] not in pos:
            pos[w["text"]] = w["x0"]
    if not all(k in pos for k in _KOPF):
        return None
    return {"wohnort": pos["Wohnort"], "klub": pos["Schwingklub"], "status": pos.get("Status")}


def _rangzeile(texte: list[str]) -> tuple[str, float, str | None, int] | None:
    """(Rang, Punkte, Resultat, Index des ersten Namens-Worts) oder None."""
    if len(texte) < 3 or not _RANG_RE.match(texte[0]):
        return None
    m = _PUNKTE_RE.match(texte[1])
    if not m:
        return None
    punkte = float(m.group(1))
    rest = m.group(2)
    # Angeklebtes Resultat ("58.75S-+++++") -- Zeichen ausserhalb +-o0 davor weg.
    if rest:
        resultat = re.sub(r"[^+\-o0]", "", rest) or None
        return texte[0], punkte, resultat, 2
    if _RESULTAT_RE.match(texte[2]):
        return texte[0], punkte, texte[2], 3
    return texte[0], punkte, None, 2


def _name_und_merkmale(woerter: list[dict]) -> tuple[str, str | None, int]:
    """Namensteil: "Stucki Marcel (1), S *" -> (Name, Senn/Turner, Sterne)."""
    name: list[str] = []
    senne_turner = None
    sterne = 0
    nach_komma = False
    for w in woerter:
        t = w["text"]
        m = _STERN_SUFFIX_RE.match(t)
        if _STERNE_RE.match(t):
            sterne = max(sterne, len(t))
            continue
        if m and not _STERNE_RE.match(t):
            t = m.group(1)
            sterne = max(sterne, len(m.group(2)))
        if nach_komma:
            if t in _SENNE_TURNER:
                senne_turner = _SENNE_TURNER[t]
            continue
        if t.endswith(","):
            name.append(t[:-1])
            nach_komma = True
        else:
            name.append(t)
    return " ".join(x for x in name if x), senne_turner, sterne


def parse_seiten(seiten: list[list[dict]]) -> list[dict]:
    """Wortlisten je Seite (pdfplumber extract_words) -> Ranglisten-Einträge."""
    eintraege: list[dict] = []
    spalten = None
    for woerter in seiten:
        spalten = _spalten(woerter) or spalten  # Folgeseiten ohne Kopf: letzte gilt
        if spalten is None:
            continue
        letzte: dict | None = None
        letzte_top = None
        for zeile in _zeilen(woerter):
            texte = [w["text"] for w in zeile]
            status = [t for t in texte if t in STATUS_WOERTER]
            if status and len(status) == len(texte):
                # Reine Statuszeile: gehört zur Rangzeile direkt darüber.
                if letzte is not None and zeile[0]["top"] - letzte_top <= _STATUSZEILE_ABSTAND:
                    letzte["status"] = letzte["status"] or status[0]
                continue
            kopf = _rangzeile(texte)
            if kopf is None:
                continue
            rang, punkte, resultat, start = kopf
            rest = [w for w in zeile[start:] if w["text"] not in STATUS_WOERTER]
            grenze_wohnort = spalten["wohnort"] - _SPALTEN_TOLERANZ
            grenze_klub = spalten["klub"] - _SPALTEN_TOLERANZ
            name, senne_turner, sterne = _name_und_merkmale(
                [w for w in rest if w["x0"] < grenze_wohnort]
            )
            if not name:
                continue
            wohnort = " ".join(w["text"] for w in rest if grenze_wohnort <= w["x0"] < grenze_klub)
            klub = " ".join(w["text"] for w in rest if w["x0"] >= grenze_klub)
            letzte = {
                "rang": rang,
                "punkte": punkte,
                "resultat": resultat,
                "name": name,
                "senne_turner": senne_turner,
                "abzeichen": sterne,
                "wohnort": wohnort or None,
                "schwingklub": klub or None,
                "status": status[0] if status else None,
            }
            letzte_top = zeile[0]["top"]
            eintraege.append(letzte)
    return eintraege


def parse_rangliste(pdf_bytes: bytes) -> list[dict]:
    import pdfplumber

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        seiten = [p.extract_words() for p in pdf.pages]
    eintraege = parse_seiten(seiten)
    if not eintraege:
        raise RanglisteUnlesbar("keine Rangzeilen erkannt")
    return eintraege


def mit_kranz(eintraege: list[dict]) -> list[dict]:
    """Ergänzt ``kranz`` (bool): hat dieser Schwinger hier einen Kranz gewonnen?

    Der Kranz geht an alle ab einer Punkteschwelle -- vermessen an allen
    Kranzfesten der Stichprobe: jeder Markierte hatte mehr Punkte als jeder
    Unmarkierte, ohne Ausnahme. Das Eidgenössische markiert aber nur
    NEU-Eidgenossen; wer schon Eidgenosse war, bekommt dort keinen Status,
    obwohl er den Kranz gewinnt. Darum gilt die Schwelle: niedrigste Punktzahl
    eines Markierten. ESAF 2025: 17 Neueidgenossen + 23 bisherige = 40 von
    269 (14.9 %), passend zur üblichen Kranzquote von 14-18 %.

    Ohne jede Markierung (Regionalfeste, Kilchberg): kein Kranz vergeben.
    """
    markiert = [e["punkte"] for e in eintraege if e.get("status")]
    schwelle = min(markiert) if markiert else None
    return [{**e, "kranz": schwelle is not None and e["punkte"] >= schwelle} for e in eintraege]


def kranzquote(eintraege: list[dict]) -> float:
    return sum(1 for e in eintraege if e.get("kranz")) / len(eintraege) if eintraege else 0.0


def nach_name(eintraege: list[dict]) -> dict[str, dict]:
    """Name -> Eintrag (für Tests/Diagnose; Duplikate: der besser platzierte)."""
    out: dict[str, dict] = {}
    for e in eintraege:
        out.setdefault(e["name"], e)
    return out


def zaehle(eintraege: list[dict]) -> dict:
    """Kurze Kennzahlen einer Rangliste (Diagnose)."""
    z = defaultdict(int)
    for e in eintraege:
        z["n"] += 1
        z["mit_klub"] += bool(e.get("schwingklub"))
        z["kranz"] += bool(e.get("kranz"))
    return dict(z)
