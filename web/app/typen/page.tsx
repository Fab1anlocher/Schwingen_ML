"use client";

// Seite "Typen": Stil-Typen (stiltypen.json aus pipeline/stiltypen.py).
// Nicht wie stark ein Schwinger ist, sondern wie er seine Gänge entscheidet:
// Plattwurf und Gestellt, beides gegen die Erwartung aus Gegnern und Fest.

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { ladeSchwinger, ladeStilTypen } from "@/lib/data";
import type { Schwinger, StilTyp, StilTypenArtifact } from "@/lib/types";
import { StilLandkarte } from "@/components/StilLandkarte";
import { SchwingerSuche } from "@/components/SchwingerSuche";
import { STIL_TYPEN, prozentpunkte, schwungName, stilTypName, zahl } from "@/lib/labels";

function rText(r: number | null): string {
  return r === null ? "–" : r.toFixed(2);
}

/** Stärke eines Zusammenhangs in Worten (Betrag von r). */
function staerke(r: number | null): string {
  if (r === null) return "nicht messbar";
  const a = Math.abs(r);
  if (a < 0.1) return "praktisch nicht";
  if (a < 0.3) return "schwach";
  if (a < 0.5) return "mässig";
  return "deutlich";
}

export default function Typen() {
  const [daten, setDaten] = useState<StilTypenArtifact | null>(null);
  const [schwinger, setSchwinger] = useState<Schwinger[]>([]);
  const [fehler, setFehler] = useState<string | null>(null);
  const [markiert, setMarkiert] = useState<string>("");
  const [hervorTyp, setHervorTyp] = useState<string | null>(null);

  useEffect(() => {
    ladeStilTypen().then(setDaten).catch((e) => setFehler(String(e)));
    ladeSchwinger().then(setSchwinger).catch(() => {});
  }, []);

  const schwingerById = useMemo(
    () => Object.fromEntries(schwinger.map((s) => [s.id, s])),
    [schwinger]
  );
  const punktById = useMemo(
    () => Object.fromEntries((daten?.punkte ?? []).map((p) => [p.schwinger_id, p])),
    [daten]
  );
  // Suche nur über Schwinger mit Typ, nach Elo (Vorschläge bei leerem Feld).
  const suchliste = useMemo(
    () =>
      (daten?.punkte ?? [])
        .slice()
        .sort((a, b) => b.elo - a.elo)
        .map((p) => schwingerById[p.schwinger_id])
        .filter((s): s is Schwinger => Boolean(s)),
    [daten, schwingerById]
  );

  if (fehler) return <p className="warn">Fehler beim Laden: {fehler}</p>;
  if (!daten) return <p className="loading">Schwingertypen werden geladen …</p>;

  const auswahl = markiert ? punktById[markiert] : undefined;
  const auswahlName = auswahl ? schwingerById[auswahl.schwinger_id]?.name : undefined;
  const typen: StilTyp[] = daten.typen;
  const pr = daten.pruefung;

  return (
    <div>
      <span className="eyebrow">Stil-Analyse</span>
      <h1>Schwingertypen</h1>
      <p className="subtitle">
        Nicht wie stark einer ist, sondern <em>wie</em> er seine Gänge entscheidet: Gewinnt er
        gern mit dem Plattwurf? Stellt er oft? Beides ist gemessen und gegen das gerechnet, was
        seine Gegner und das Fest erwarten lassen. So ist ein Typ keine Frage der Stärke.
      </p>

      <div className="panel stil-suche">
        <label htmlFor="stil-suche" className="stil-suche-frage">Welcher Typ ist …?</label>
        <SchwingerSuche
          id="stil-suche"
          label="Schwinger"
          schwinger={suchliste}
          value={markiert}
          onChange={setMarkiert}
          hideLabel
        />
        {auswahl && (
          <div className="stil-antwort">
            <p>
              <strong>{auswahlName}</strong> ist ein{" "}
              <strong className="stil-antwort-typ">{stilTypName(auswahl.typ)}</strong>.{" "}
              {STIL_TYPEN[auswahl.typ]?.satz}
            </p>
            <p className="muted small">
              Plattwurf in {Math.round(auswahl.plattwurf_quote * 100)}% seiner Siege (erwartet{" "}
              {Math.round(auswahl.plattwurf_erwartet * 100)}%, {prozentpunkte(auswahl.plattwurf)}{" "}
              nach Schrumpfung) · gestellt in {Math.round(auswahl.gestellt_quote * 100)}% seiner
              Gänge (erwartet {Math.round(auswahl.gestellt_erwartet * 100)}%,{" "}
              {prozentpunkte(auswahl.gestellt)}) · {auswahl.n_siege} Siege, {auswahl.n_gaenge}{" "}
              Gänge · <Link href={`/?a=${encodeURIComponent(auswahl.schwinger_id)}`}>zur Prognose</Link>
            </p>
          </div>
        )}
      </div>

      <div className="panel">
        <StilLandkarte
          daten={daten}
          schwingerById={schwingerById}
          markiert={markiert || null}
          hervorTyp={hervorTyp}
          onWaehle={setMarkiert}
        />
      </div>

      <div className="typen-karten">
        {typen.map((t) => {
          const info = STIL_TYPEN[t.typ];
          const anteil = t.n / daten.n_schwinger;
          return (
            <div
              key={t.typ}
              className={`typen-karte${hervorTyp === t.typ ? " typen-karte-aktiv" : ""}`}
              onMouseEnter={() => setHervorTyp(t.typ)}
              onMouseLeave={() => setHervorTyp((h) => (h === t.typ ? null : h))}
            >
              <div className="row" style={{ justifyContent: "space-between", alignItems: "baseline" }}>
                <strong className="typen-name">{info?.name ?? t.typ}</strong>
                <span className="muted small">
                  {t.n} Schwinger · {Math.round(anteil * 100)}%
                </span>
              </div>
              <p className="typen-auszeichnung">{info?.satz}</p>
              <p className="muted small" style={{ margin: "0.2rem 0" }}>
                Plattwurf Ø {Math.round(t.plattwurf_quote_avg * 100)}% der Siege · gestellt Ø{" "}
                {Math.round(t.gestellt_quote_avg * 100)}% · Elo Ø {Math.round(t.elo_avg)}
                {t.gewicht_avg !== null && <> · {Math.round(t.gewicht_avg)} kg Ø ({t.n_physis} mit Porträt)</>}
                {t.top_schwuenge.length > 0 && <> · bevorzugt {t.top_schwuenge.map(schwungName).join(", ")}</>}
              </p>
              {schwingerById[t.ausgepraegteste] && (
                <p className="small" style={{ margin: "0.35rem 0 0.2rem" }}>
                  Am ausgeprägtesten:{" "}
                  <button type="button" className="link-btn" onClick={() => setMarkiert(t.ausgepraegteste)}>
                    {schwingerById[t.ausgepraegteste].name}
                  </button>
                </p>
              )}
              <div className="row" style={{ marginTop: "0.3rem", gap: "0.4rem", flexWrap: "wrap" }}>
                <span className="muted small">Bekannteste:</span>
                {t.bekannteste.map((sid) =>
                  schwingerById[sid] ? (
                    <button key={sid} type="button" className="badge" onClick={() => setMarkiert(sid)}>
                      {schwingerById[sid].name}
                    </button>
                  ) : null
                )}
              </div>
            </div>
          );
        })}
      </div>

      <details className="methodik" style={{ marginTop: "1rem" }}>
        <summary>So ist es gemessen</summary>
        <p>
          Grundlage sind {zahl(daten.n_gaenge)} Gänge und{" "}
          {zahl(daten.n_siege)} Siege mit Note, in denen beide Schwinger schon
          ein Elo mit mindestens zehn Gängen hatten. Einen Typ bekommt, wer aktiv ist und
          mindestens {daten.mindestens.gaenge} Gänge und {daten.mindestens.siege} Siege hat:{" "}
          {daten.n_schwinger} Schwinger.
        </p>
        <ul>
          <li>
            <strong>Plattwurf:</strong> Anteil der Siege mit der 10.00 (im Schnitt{" "}
            {Math.round(daten.plattwurf_basis * 100)}%) gegenüber der Erwartung. Gegen deutlich
            Schwächere wirft jeder öfter platt, und manche Feste benoten grosszügiger. Darum
            rechnet die Erwartung den Elo-Abstand, die eigene Stärke und die Quote des Fests (ohne
            die eigenen Siege) heraus. Mutmassliche Schlussgänge zählen nicht: Dort sind
            10.00/8.75 vorgeschrieben.
          </li>
          <li>
            <strong>Gestellt:</strong> Anteil gestellter Gänge (im Schnitt{" "}
            {Math.round(daten.gestellt_basis * 100)}%) gegenüber der Erwartung aus Elo-Abstand,
            Niveau der Paarung (zwei Starke stellen öfter) und Quote des Fests.
          </li>
          <li>
            Beide Werte sind mit 20 erfundenen Durchschnitts-Gängen gemischt, damit wenige Gänge
            keine Extremwerte erzeugen. Die Grenze eines Typs liegt bei{" "}
            {daten.schwelle_z.toFixed(1)} Standardabweichungen: {prozentpunkte(daten.schwelle_plattwurf)}{" "}
            beim Plattwurf, {prozentpunkte(daten.schwelle_gestellt)} beim Gestellt.
          </li>
        </ul>
        <p>
          <strong>Ist das eine Eigenschaft der Person?</strong> Verteilt man die Gänge jedes
          Schwingers abwechselnd auf zwei Hälften, hängen die Werte der Hälften zusammen:
          Plattwurf r = {rText(pr.haelften_r_plattwurf)}, Gestellt r = {rText(pr.haelften_r_gestellt)}{" "}
          (0 = Zufall, 1 = immer gleich). Mit dem Elo hängt der Plattwurf{" "}
          {staerke(pr.r_elo_plattwurf)} zusammen (r = {rText(pr.r_elo_plattwurf)}), das Gestellt{" "}
          {staerke(pr.r_elo_gestellt)} (r = {rText(pr.r_elo_gestellt)}); die beiden Achsen
          untereinander {staerke(pr.r_achsen)} (r = {rText(pr.r_achsen)}).
        </p>
        <p className="muted small">
          Bis Oktober 2026 standen hier Gruppen aus einem K-Means über Körperbau, Elo, Erfahrung,
          Alter, Kranzstatus und Schwünge. Die Daten bilden aber keine natürlichen Gruppen
          (Silhouette 0.24): Heraus kamen „die Starken" (82), „alle anderen" (434) und zehn, die
          den Schlungg mögen. Stärke zeigen Elo und Kränze schon. Die ähnlichen Schwinger im
          Profil kommen weiterhin aus dem Porträt-Profil.
        </p>
      </details>
    </div>
  );
}
