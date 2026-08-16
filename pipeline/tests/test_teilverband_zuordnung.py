"""Fest-Name -> Teilverband (web/lib/teilverband.ts), geprüft an echten Daten.

Die Zuordnung entscheidet, wer in der Favoritenliste eines kommenden Fests
auftaucht. Stimmt sie nicht, zeigt die Feste-Seite Schwinger, die dort gar
nicht startberechtigt sind -- real passiert: an einem Nordwestschweizer
Teilverbandsfest standen sechs Schwinger aus Bern und der Nordostschweiz.

Der Test liest die Muster aus der TypeScript-Datei, damit App und Test nicht
auseinanderlaufen, und validiert sie gegen die tatsächliche Teilnehmer-
zusammensetzung aller erfassten Kantonal- und Teilverbandsfeste.
"""
from __future__ import annotations

import collections
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
TS_DATEI = ROOT / "web" / "lib" / "teilverband.ts"
ARTIFACTS = ROOT / "artifacts"

# Fest-Typen mit regional beschränktem Teilnehmerfeld.
BESCHRAENKTE_TYPEN = {"teilverband", "kantonal"}
OFFENE_TYPEN = {"berg", "eidgenoessisch"}


def _muster_aus_typescript() -> list[tuple[str, re.Pattern]]:
    """Liest TEILVERBAND_MUSTER aus der TS-Datei (JS- und Python-Regex-kompatibel)."""
    text = TS_DATEI.read_text(encoding="utf-8")
    block = re.search(r"TEILVERBAND_MUSTER[^=]*=\s*\[(.*?)\n\];", text, re.DOTALL)
    assert block, "TEILVERBAND_MUSTER nicht gefunden"
    paare = re.findall(r'"([A-Za-z]+)",\s*\n\s*/(.+?)/,', block.group(1))
    assert paare, "Keine Muster geparst"
    return [(tv, re.compile(rx)) for tv, rx in paare]


def _teilverband(name: str, typ: str, muster) -> str | None:
    if typ not in BESCHRAENKTE_TYPEN:
        return None
    n = name.lower()
    for tv, rx in muster:
        if rx.search(n):
            return tv
    return None


@pytest.fixture(scope="module")
def echte_feste():
    """(Fest, empirisch dominierender Teilverband) aus den eingecheckten Artefakten."""
    events_pfad = ARTIFACTS / "events.json"
    kk_pfad = ARTIFACTS / "kopf_an_kopf.json"
    if not events_pfad.exists() or not kk_pfad.exists():
        pytest.skip("Artefakte nicht vorhanden (z.B. nach --source synth)")

    schwinger = {s["id"]: s for s in json.loads(
        (ARTIFACTS / "schwinger.json").read_text(encoding="utf-8"))["schwinger"]}
    events = {e["id"]: e for e in json.loads(
        events_pfad.read_text(encoding="utf-8"))["vergangene"]}
    kk = json.loads(kk_pfad.read_text(encoding="utf-8"))
    inv = {v: k for k, v in kk["index"].items()}
    idx2id = {v: k for k, v in kk["event_index"].items()}

    teilnehmer = collections.defaultdict(set)
    for key, treffer in kk["paare"].items():
        a, b = key.split("_")
        for eidx, _ in treffer:
            eid = idx2id.get(eidx)
            teilnehmer[eid].add(inv[int(a)])
            teilnehmer[eid].add(inv[int(b)])

    out = []
    for eid, ids in teilnehmer.items():
        event = events.get(eid)
        if not event:
            continue
        tvs = [schwinger[i].get("teilverband") for i in ids
               if i in schwinger and schwinger[i].get("teilverband")]
        if not tvs:
            continue
        out.append((event, collections.Counter(tvs).most_common(1)[0][0]))
    return out


def test_zuordnung_trifft_jedes_erfasste_kantonal_und_teilverbandsfest(echte_feste):
    muster = _muster_aus_typescript()
    relevant = [(e, emp) for e, emp in echte_feste if e["typ"] in BESCHRAENKTE_TYPEN]
    assert len(relevant) >= 100, f"zu wenige Feste zum Prüfen: {len(relevant)}"

    fehler = []
    for event, empirisch in relevant:
        hergeleitet = _teilverband(event["name"], event["typ"], muster)
        if hergeleitet != empirisch:
            fehler.append(f"{event['name']}: hergeleitet={hergeleitet} empirisch={empirisch}")
    assert not fehler, "Fehlzuordnungen:\n" + "\n".join(fehler)


def test_offene_feste_werden_nicht_eingeschraenkt(echte_feste):
    """Berg- und Eidgenössische Feste sind gesamtschweizerisch (33-55 % grösster
    Teilverband) -- dort darf die Liste nicht gefiltert werden."""
    muster = _muster_aus_typescript()
    for event, _ in echte_feste:
        if event["typ"] in OFFENE_TYPEN:
            assert _teilverband(event["name"], event["typ"], muster) is None, event["name"]


def test_wortgrenzen_verhindern_teilwort_treffer():
    """Regression: "urner" steckt in "Solothurner" -- ohne Wortgrenze galt ein
    Nordwestschweizer Fest als Innerschweizer."""
    muster = _muster_aus_typescript()
    assert _teilverband("Solothurner Kantonalschwingfest Grenchen 2025", "kantonal", muster) \
        == "Nordwestschweiz"
    # "Jurassisch" steckt in "Bern-Jurassisch" -- Bern muss zuerst greifen.
    assert _teilverband("Bern-Jurassisches Schwingfest Werdtberg 2026", "kantonal", muster) \
        == "Bern"


def test_alle_fuenf_teilverbaende_abgedeckt():
    assert {tv for tv, _ in _muster_aus_typescript()} == {
        "Bern", "Innerschweiz", "Nordostschweiz", "Nordwestschweiz", "Suedwestschweiz"
    }
