"use client";

import type { Prognose } from "@/lib/types";

const LABELS: Record<string, string> = {
  sieg_a: "Sieg A",
  gestellt: "Gestellt",
  sieg_b: "Sieg B",
};

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
  const maxStaerke = Math.max(...beitraege.map((b) => b.staerke), 1e-6);

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
        <span>◧ {nameA}</span>
        <span>Gestellt</span>
        <span>{nameB} ◨</span>
      </div>

      <div className="quote-row">
        {(["sieg_a", "gestellt", "sieg_b"] as const).map((k) => (
          <div className="quote-card" key={k}>
            <div className="k">{LABELS[k]}</div>
            <div className="p">{pct(p[k])}</div>
            <div className="q">Quote {quote[k].toFixed(2)}</div>
          </div>
        ))}
      </div>

      {unsicher && (
        <div className="warn">
          ⚠ Mindestens ein Schwinger hat wenige erfasste Gänge — die Prognose ist
          entsprechend unsicher.
        </div>
      )}

      <h2>Warum diese Prognose?</h2>
      <div className="panel">
        {beitraege.length === 0 && (
          <p className="muted small">Keine ausgeprägten Merkmalsbeiträge.</p>
        )}
        {beitraege.map((b, i) => (
          <div className="beitrag" key={i}>
            <span className={`pill ${b.richtung === "a" ? "pill-a" : "pill-b"}`}>
              {b.richtung === "a" ? nameA : nameB}
            </span>
            <span className="small beitrag-label">{b.label}</span>
            <div className="contrib-track">
              <div
                className="contrib-fill"
                style={{
                  width: `${(b.staerke / maxStaerke) * 100}%`,
                  background: b.richtung === "a" ? "var(--a)" : "var(--b)",
                }}
              />
            </div>
          </div>
        ))}
      </div>
      <p className="muted small" style={{ marginTop: "0.75rem" }}>
        Balken zeigen, welches Merkmal wie stark zugunsten von A oder B wirkt.
      </p>
    </div>
  );
}
