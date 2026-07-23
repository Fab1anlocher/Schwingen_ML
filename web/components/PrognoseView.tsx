"use client";

import type { Prognose } from "@/lib/types";

const LABELS: Record<string, string> = {
  sieg_a: "Sieg A",
  gestellt: "Gestellt",
  sieg_b: "Sieg B",
};

// Feste statt relative Skala: sonst wäre der stärkste Balken einer Paarung
// immer voll ausgeschlagen, egal ob er 2 oder 40 Prozentpunkte ausmacht --
// genau das würde verschleiern, wie dominant z.B. der Rating-Vorsprung
// typischerweise ist. 40 %-Pkt. ist empirisch der ~p95-Wert des jeweils
// stärksten Merkmals über 3000 zufällige echte Paarungen -- bei sehr
// einseitigen Merkmalen darf ein Balken darum voll ausschlagen (Clamping).
const BEITRAG_SKALA_MAX_PP = 40;

export function PrognoseView({
  prognose,
  nameA,
  nameB,
}: {
  prognose: Prognose;
  nameA: string;
  nameB: string;
}) {
  const { p, quote, beitraege, unsicher } = prognose;
  const pct = (v: number) => `${(v * 100).toFixed(0)}%`;

  const quoteMeta = [
    { key: "sieg_a", klasse: "quote-card-a" },
    { key: "gestellt", klasse: "quote-card-draw" },
    { key: "sieg_b", klasse: "quote-card-b" },
  ] as const;

  return (
    <div>
      <div className="probbar" role="img" aria-label="Wahrscheinlichkeiten">
        <div className="seg-a" style={{ flexBasis: pct(p.sieg_a) }}>
          {p.sieg_a > 0.08 ? pct(p.sieg_a) : ""}
        </div>
        <div className="seg-draw" style={{ flexBasis: pct(p.gestellt) }}>
          {p.gestellt > 0.08 ? pct(p.gestellt) : ""}
        </div>
        <div className="seg-b" style={{ flexBasis: pct(p.sieg_b) }}>
          {p.sieg_b > 0.08 ? pct(p.sieg_b) : ""}
        </div>
      </div>
      <div className="prob-legend">
        <span>Sieg {nameA}</span>
        <span>Gestellt</span>
        <span>Sieg {nameB}</span>
      </div>

      <div className="quote-row">
        {quoteMeta.map(({ key, klasse }) => (
          <div className={`quote-card ${klasse}`} key={key}>
            <div className="k">{LABELS[key]}</div>
            <div className="p">{pct(p[key])}</div>
            <div className="q">Quote {quote[key].toFixed(2)}</div>
          </div>
        ))}
      </div>

      {unsicher && (
        <div className="warn">
          ⚠ Mindestens ein Schwinger hat wenige erfasste Gänge — die Prognose ist
          entsprechend unsicher.
        </div>
      )}

      <Spannungsanzeige p={p} />

      <h2>Warum diese Prognose?</h2>
      <p className="section-hint">
        Jeder Balken zeigt, wie stark ein Merkmal zugunsten von{" "}
        <strong style={{ color: "var(--accent)" }}>{nameA}</strong> (rot, rechts) oder{" "}
        <strong style={{ color: "var(--ink)" }}>{nameB}</strong> (dunkel, links) wirkt — in
        Prozentpunkten der Siegchance.
      </p>
      <div className="panel">
        {beitraege.length === 0 && (
          <p className="muted small">Keine ausgeprägten Merkmalsbeiträge.</p>
        )}
        {beitraege.map((b, i) => {
          const anteil = Math.min(b.staerke / BEITRAG_SKALA_MAX_PP, 1) * 50;
          const favorit = b.richtung === "a" ? nameA : nameB;
          return (
            <div className="beitrag" key={i}>
              <div className="beitrag-labels">
                <div className="beitrag-titel">{b.titel}</div>
                {b.unterzeile && <div className="beitrag-sub">{b.unterzeile}</div>}
              </div>
              <div className="beitrag-track" aria-hidden>
                <div
                  className={`beitrag-fill beitrag-fill-${b.richtung}`}
                  style={{ width: `${anteil}%` }}
                />
              </div>
              <div className={`beitrag-name beitrag-name-${b.richtung}`}>
                {favorit}
                <span className="beitrag-wert">+{b.staerke.toFixed(1)} %-Pkt.</span>
              </div>
            </div>
          );
        })}
      </div>
      <p className="muted small" style={{ marginTop: "0.85rem" }}>
        „+X %-Pkt.“ = um so viele Prozentpunkte würde sich {nameA}s Siegchance ändern, gäbe es
        bei genau diesem Merkmal keinen Unterschied zwischen den beiden (alle anderen Merkmale
        bleiben gleich). Balkenlänge auf fester Skala, damit sie auch zwischen verschiedenen
        Paarungen vergleichbar ist.
      </p>
    </div>
  );
}

/** Fairness-/Spannungsgrad: normierte Entropie der 3-Klassen-Wahrscheinlichkeit.
 * 100% = völlig offen (alle drei gleich wahrscheinlich), 0% = eindeutiger Favorit. */
function spannungsgrad(p: Record<string, number>): number {
  const werte = Object.values(p).filter((v) => v > 0);
  const entropie = -werte.reduce((s, v) => s + v * Math.log(v), 0);
  return entropie / Math.log(3);
}

function Spannungsanzeige({ p }: { p: Record<string, number> }) {
  const grad = spannungsgrad(p);
  const label =
    grad > 0.85
      ? "Hochspannung — völlig offen"
      : grad > 0.6
      ? "Ausgeglichenes Duell"
      : grad > 0.35
      ? "Klarer Favorit"
      : "Eindeutige Sache";
  return (
    <div
      className="spannung-wrap"
      title="Basiert auf der Entropie der Prognose (0 = klar, 100% = völlig offen)"
    >
      <div className="spannung-track">
        <div className="spannung-fill" style={{ width: `${(grad * 100).toFixed(0)}%` }} />
      </div>
      <span className="spannung-label">
        ⚡ {label} ({(grad * 100).toFixed(0)}%)
      </span>
    </div>
  );
}
