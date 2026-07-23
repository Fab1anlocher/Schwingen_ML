"""esv.ch-Datenlader: Ranglisten -> (Schwinger, Events, Roh-Gänge) im
Pipeline-Schema, mit stabiler esv-uid als Schwinger-Identität (Phase 4).

Ersetzt schlussgang.ch als Primärquelle. Aus jeder Aktiv-Rangliste entstehen:
  - ein Event (id = anlass_id, typ = Fest-Stufe für Elo-Gewichtung),
  - Schwinger (id = esv-uid; Verband -> Teilverband; Karriere-Sterne ->
    Kranzstatus). Physis/Alter/Schwünge kommen optional aus den Porträts.
  - RohGangEintrag je Gang-Perspektive (Gegner via slug->uid aufgelöst).

Ohne Porträt-Anreicherung fehlen Gewicht/Grösse/Jahrgang/Schwünge (=None); das
Modell trainiert dann auf Elo/Kranz/Form/Kopf-an-Kopf. Mit ``mit_portraets``
werden die Stammdaten je Schwinger (einmalig gecacht) nachgeladen.
"""
from __future__ import annotations

from typing import Optional

from ..labels import RohGangEintrag
from ..schema import Event, Schwinger


def _log(msg: str) -> None:
    """Fortschritts-Ausgabe, die auch bei Umleitung in eine Datei sofort
    erscheint (flush) -- so sieht man den Backfill live im Terminal."""
    print(msg, flush=True)


_TEILVERBAND_PREFIX = {
    "BKSV": "Bern",
    "ISV": "Innerschweiz",
    "NOS": "Nordostschweiz",
    "NOSV": "Nordostschweiz",
    "NWSV": "Nordwestschweiz",
    "NWS": "Nordwestschweiz",
    "SWS": "Suedwestschweiz",
    "SWSV": "Suedwestschweiz",
}


def _teilverband(verband: Optional[str]) -> Optional[str]:
    if not verband:
        return None
    return _TEILVERBAND_PREFIX.get(verband.split()[0].upper())


def _kranzstatus(sterne: int) -> str:
    # esv-Kranzkennung (Sterne): *** ~ Eidgenössischer Kranzgewinner, 1-2 ~
    # Kranzer, 0 ~ kein. König lässt sich hier nicht ableiten (nur aus ESAF-Sieg
    # / Porträt) -> ggf. später aus Porträt anheben.
    if sterne >= 3:
        return "eidgenosse"
    if sterne >= 1:
        return "kranzer"
    return "kein"


_KRANZ_RANG = {"kein": 0, "kranzer": 1, "eidgenosse": 2, "koenig": 3}


def lade_esv_daten(
    von_jahr: int,
    bis_jahr: int,
    *,
    nur_aktiv: bool = True,
    max_feste: Optional[int] = None,
    aktuelles_jahr: Optional[int] = None,
    mit_portraets: bool = False,
    log=_log,
):
    """(schwinger: dict[str,Schwinger], events: list[Event], roh: list[RohGangEintrag])."""
    from .esv_fetch import ESV_CACHE, feste_im_zeitraum, hole_rangliste
    from .esv_ranglisten import parse_rangliste

    refs = feste_im_zeitraum(von_jahr, bis_jahr, nur_aktiv=nur_aktiv, aktuelles_jahr=aktuelles_jahr)
    refs = [r for r in refs if r.datum]  # ohne Datum kein zeitliches Modell
    refs.sort(key=lambda r: r.datum or "")
    if max_feste:
        refs = refs[:max_feste]
    n_total = len(refs)
    log(f"      {n_total} Aktiv-Feste {von_jahr}-{bis_jahr} -- lade Ranglisten ...")

    schwinger: dict[str, Schwinger] = {}
    slug_zu_uid: dict[str, str] = {}
    events: list[Event] = []
    geparste: list = []
    n_gaenge_roh = 0

    for i, ref in enumerate(refs, 1):
        aus_cache = (ESV_CACHE / f"anlass_{ref.anlass_id}.html").exists()
        try:
            html = hole_rangliste(ref.anlass_id, erzwinge_neu=False)
            rl = parse_rangliste(html, anlass_id=ref.anlass_id)
        except Exception as e:  # noqa: BLE001 - einzelnes Fest darf den Lauf nicht stoppen
            log(f"      [{i}/{n_total}] {ref.name}: nicht ladbar/parsbar: {e}")
            continue
        # Fortschrittszeile je Fest (Cache-Treffer vs. neu geladen).
        marker = "cache" if aus_cache else " neu "
        log(f"      [{i}/{n_total}] {marker} {ref.datum} {ref.name[:42]:42} "
            f"({len(rl.schwinger)} Schw., {len(rl.gaenge)} Gaenge) "
            f"| total {len(schwinger)} Schwinger")
        if not rl.schwinger:
            continue
        n_gaenge_roh += len(rl.gaenge)
        events.append(
            Event(id=ref.anlass_id, name=rl.name or ref.name, datum=rl.datum or ref.datum,
                  typ=ref.stufe, quelle="esv.ch", ort=ref.ort)
        )
        for s in rl.schwinger:
            if s.slug:
                slug_zu_uid[s.slug] = s.uid
            neuer_status = _kranzstatus(s.karriere_sterne)
            if s.uid not in schwinger:
                schwinger[s.uid] = Schwinger(
                    id=s.uid, name=s.name, kranzstatus=neuer_status,
                    teilverband=_teilverband(s.verband), kanton=s.verband,
                    quellen=["esv.ch"],
                )
            else:
                vorhanden = schwinger[s.uid]
                if _KRANZ_RANG.get(neuer_status, 0) > _KRANZ_RANG.get(vorhanden.kranzstatus, 0):
                    vorhanden.kranzstatus = neuer_status
        geparste.append((ref, rl))

    roh: list[RohGangEintrag] = []
    ungeloest = 0
    for ref, rl in geparste:
        kranz_uids = {s.uid for s in rl.schwinger if s.kranz_hier}
        for g in rl.gaenge:
            gegner_uid = slug_zu_uid.get(g.gegner_slug or "")
            if not gegner_uid or gegner_uid == g.schwinger_uid:
                ungeloest += 1
                continue
            roh.append(
                RohGangEintrag(
                    event_id=ref.anlass_id, datum=rl.datum, schwinger_id=g.schwinger_uid,
                    gegner_id=gegner_uid, symbol=g.symbol, note=g.punkte,
                    fest_typ=ref.stufe, kranz=(g.schwinger_uid in kranz_uids),
                )
            )
    log(f"      {len(schwinger)} Schwinger, {len(events)} Events, {len(roh)} Roh-Gänge "
        f"({ungeloest} Gegner nicht auflösbar)")

    if mit_portraets:
        _reichere_portraets_an(schwinger, slug_zu_uid, log=log)

    return schwinger, events, roh


def _reichere_portraets_an(schwinger: dict, slug_zu_uid: dict, *, log=_log) -> None:
    """Lädt je Schwinger das Porträt (gecacht) und ergänzt Stammdaten
    (Jahrgang, Gewicht, Grösse, Senne/Turner, Schwünge)."""
    from .esv_fetch import hole_portraet
    from .esv_portraet import parse_portraet

    uid_zu_slug = {uid: slug for slug, uid in slug_zu_uid.items()}
    n = 0
    for uid, s in schwinger.items():
        slug = uid_zu_slug.get(uid)
        if not slug:
            continue
        try:
            p = parse_portraet(hole_portraet(slug), slug)
        except Exception:  # noqa: BLE001
            continue
        s.jahrgang = p.jahrgang
        s.groesse_cm = p.groesse_cm
        s.gewicht_kg = p.gewicht_kg
        s.senne_turner = p.senne_turner
        s.bevorzugte_schwuenge = p.bevorzugte_schwuenge
        if p.schwingklub:
            s.schwingklub = p.schwingklub
        n += 1
        if n % 200 == 0:
            log(f"      Porträts angereichert: {n}/{len(schwinger)}")
    log(f"      Porträt-Anreicherung fertig: {n} Schwinger")
