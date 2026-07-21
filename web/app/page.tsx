"use client";

import { useEffect, useMemo, useState } from "react";
import { ladeEvents, ladeModel, ladeRatings, ladeSchwinger } from "@/lib/data";
import { prognostiziere } from "@/lib/inference";
import type { ModelArtifact, RatingsArtifact, Schwinger, Prognose } from "@/lib/types";
import { PrognoseView } from "@/components/PrognoseView";
import { SchwingerSuche } from "@/components/SchwingerSuche";
import { WasWaereWenn } from "@/components/WasWaereWenn";
import { KopfAnKopf } from "@/components/KopfAnKopf";

const FEST_TYPEN = [
  { v: "kantonal", l: "Kantonales" },
  { v: "eidgenoessisch", l: "Eidgenössisches" },
  { v: "berg", l: "Bergfest" },
  { v: "teilverband", l: "Teilverband" },
  { v: "regional", l: "Regional" },
];

export default function Home() {
  const [model, setModel] = useState<ModelArtifact | null>(null);
  const [ratings, setRatings] = useState<RatingsArtifact | null>(null);
  const [schwinger, setSchwinger] = useState<Schwinger[]>([]);
  const [aId, setAId] = useState("");
  const [bId, setBId] = useState("");
  const [festTyp, setFestTyp] = useState("kantonal");
  const [error, setError] = useState<string | null>(null);
  const [kopiert, setKopiert] = useState(false);
  const [eventInfo, setEventInfo] = useState<Record<string, { name: string; datum: string }>>({});

  useEffect(() => {
    Promise.all([ladeModel(), ladeRatings(), ladeSchwinger()])
      .then(([m, r, s]) => {
        setModel(m);
        setRatings(r);
        setSchwinger(s);
        // Aus geteiltem Link übernehmen (?a=...&b=...), sonst erste zwei als Default.
        const params = new URLSearchParams(window.location.search);
        const vorhandeneIds = new Set(s.map((sw) => sw.id));
        const aAusUrl = params.get("a");
        const bAusUrl = params.get("b");
        setAId(aAusUrl && vorhandeneIds.has(aAusUrl) ? aAusUrl : s[0]?.id ?? "");
        setBId(
          bAusUrl && vorhandeneIds.has(bAusUrl)
            ? bAusUrl
            : s[1]?.id && s[1].id !== aAusUrl
            ? s[1].id
            : s[0]?.id ?? ""
        );
      })
      .catch((e) => setError(String(e)));
    ladeEvents()
      .then((e) =>
        setEventInfo(
          Object.fromEntries(e.vergangene.map((ev) => [ev.id, { name: ev.name, datum: ev.datum }]))
        )
      )
      .catch(() => {});
  }, []);

  // URL synchron halten, damit der aktuelle Vergleich jederzeit teilbar ist.
  useEffect(() => {
    if (!aId || !bId) return;
    const url = new URL(window.location.href);
    url.searchParams.set("a", aId);
    url.searchParams.set("b", bId);
    window.history.replaceState(null, "", url.toString());
  }, [aId, bId]);

  const byId = useMemo(
    () => Object.fromEntries(schwinger.map((s) => [s.id, s])),
    [schwinger]
  );

  const eingaben = useMemo(() => {
    if (!ratings || !aId || !bId || aId === bId) return null;
    const a = byId[aId];
    const b = byId[bId];
    if (!a || !b) return null;
    const ra = ratings.ratings[aId] ?? { elo: ratings.elo_start, n_gaenge: 0 };
    const rb = ratings.ratings[bId] ?? { elo: ratings.elo_start, n_gaenge: 0 };
    return { a, b, eloA: ra.elo, eloB: rb.elo, nA: ra.n_gaenge, nB: rb.n_gaenge };
  }, [ratings, aId, bId, byId]);

  const prognose: Prognose | null = useMemo(() => {
    if (!model || !eingaben) return null;
    const { a, b, eloA, eloB, nA, nB } = eingaben;
    return prognostiziere(model, a, b, eloA, eloB, nA, nB, festTyp);
  }, [model, eingaben, festTyp]);

  if (error) return <p className="warn">Fehler beim Laden: {error}</p>;
  if (!model) return <p className="loading">Modell wird geladen …</p>;

  return (
    <div>
      <h1>Paar-Prognose</h1>
      <p className="subtitle">
        Wähle zwei Schwinger — das Modell schätzt Sieg A / Gestellt / Sieg B und erklärt,
        welche Merkmale den Ausschlag geben.
      </p>

      <div className="panel">
        <div className="grid-2">
          <SchwingerSuche id="a" label="Schwinger A" schwinger={schwinger} value={aId} onChange={setAId} />
          <SchwingerSuche id="b" label="Schwinger B" schwinger={schwinger} value={bId} onChange={setBId} />
        </div>
        <div className="row" style={{ marginTop: "0.7rem" }}>
          <button
            type="button"
            className="badge tausch-btn"
            title="Schwinger A und B tauschen"
            onClick={() => {
              setAId(bId);
              setBId(aId);
            }}
          >
            ⇄ tauschen
          </button>
          <button
            type="button"
            className={`badge teilen-btn${kopiert ? " teilen-kopiert" : ""}`}
            title="Link zu diesem Vergleich kopieren"
            onClick={async () => {
              try {
                await navigator.clipboard.writeText(window.location.href);
                setKopiert(true);
                setTimeout(() => setKopiert(false), 1800);
              } catch {
                /* Zwischenablage evtl. nicht verfügbar — kein Absturz nötig. */
              }
            }}
          >
            {kopiert ? "✓ Link kopiert" : "🔗 Link teilen"}
          </button>
        </div>
        <div style={{ marginTop: "1rem", maxWidth: 260 }}>
          <label className="field" htmlFor="typ">
            Fest-Typ
          </label>
          <select id="typ" value={festTyp} onChange={(e) => setFestTyp(e.target.value)}>
            {FEST_TYPEN.map((t) => (
              <option key={t.v} value={t.v}>
                {t.l}
              </option>
            ))}
          </select>
        </div>
      </div>

      {aId === bId && (
        <div className="warn" style={{ marginTop: "1rem" }}>
          Bitte zwei unterschiedliche Schwinger wählen.
        </div>
      )}

      {prognose && (
        <div style={{ marginTop: "1.5rem" }}>
          <PrognoseView
            prognose={prognose}
            nameA={byId[aId]?.name ?? "A"}
            nameB={byId[bId]?.name ?? "B"}
          />
          <Spannungsanzeige p={prognose.p} />
        </div>
      )}

      {prognose && (
        <>
          <h2>Kopf an Kopf</h2>
          <div className="panel">
            <KopfAnKopf
              aId={aId}
              bId={bId}
              nameA={byId[aId]?.name ?? "A"}
              nameB={byId[bId]?.name ?? "B"}
              eventInfo={eventInfo}
            />
          </div>
        </>
      )}

      {model && eingaben && (
        <>
          <h2>Was wäre, wenn …?</h2>
          <div className="panel">
            <WasWaereWenn
              model={model}
              a={eingaben.a}
              b={eingaben.b}
              eloA={eingaben.eloA}
              eloB={eingaben.eloB}
              nA={eingaben.nA}
              nB={eingaben.nB}
              festTyp={festTyp}
            />
          </div>
        </>
      )}
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
    grad > 0.85 ? "Hochspannung — völlig offen" : grad > 0.6 ? "Ausgeglichenes Duell" : grad > 0.35 ? "Klarer Favorit" : "Eindeutige Sache";
  return (
    <div className="spannung-wrap" title="Basiert auf der Entropie der Prognose (0 = klar, 100% = völlig offen)">
      <div className="spannung-track">
        <div className="spannung-fill" style={{ width: `${(grad * 100).toFixed(0)}%` }} />
      </div>
      <span className="spannung-label">
        ⚡ {label} ({(grad * 100).toFixed(0)}%)
      </span>
    </div>
  );
}
