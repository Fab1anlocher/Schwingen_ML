"use client";

import { useEffect, useMemo, useState } from "react";
import { ladeModel, ladeRatings, ladeSchwinger } from "@/lib/data";
import { prognostiziere } from "@/lib/inference";
import type { ModelArtifact, RatingsArtifact, Schwinger, Prognose } from "@/lib/types";
import { PrognoseView } from "@/components/PrognoseView";

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

  useEffect(() => {
    Promise.all([ladeModel(), ladeRatings(), ladeSchwinger()])
      .then(([m, r, s]) => {
        setModel(m);
        setRatings(r);
        setSchwinger(s);
        if (s.length >= 2) {
          setAId(s[0].id);
          setBId(s[1].id);
        }
      })
      .catch((e) => setError(String(e)));
  }, []);

  const byId = useMemo(
    () => Object.fromEntries(schwinger.map((s) => [s.id, s])),
    [schwinger]
  );

  const prognose: Prognose | null = useMemo(() => {
    if (!model || !ratings || !aId || !bId || aId === bId) return null;
    const a = byId[aId];
    const b = byId[bId];
    if (!a || !b) return null;
    const ra = ratings.ratings[aId] ?? { elo: ratings.elo_start, n_gaenge: 0 };
    const rb = ratings.ratings[bId] ?? { elo: ratings.elo_start, n_gaenge: 0 };
    return prognostiziere(model, a, b, ra.elo, rb.elo, ra.n_gaenge, rb.n_gaenge, festTyp);
  }, [model, ratings, aId, bId, byId, festTyp]);

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
          <div>
            <label className="field" htmlFor="a">
              Schwinger A
            </label>
            <select id="a" value={aId} onChange={(e) => setAId(e.target.value)}>
              {schwinger.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                  {s.jahrgang ? ` (${s.jahrgang})` : ""}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="field" htmlFor="b">
              Schwinger B
            </label>
            <select id="b" value={bId} onChange={(e) => setBId(e.target.value)}>
              {schwinger.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                  {s.jahrgang ? ` (${s.jahrgang})` : ""}
                </option>
              ))}
            </select>
          </div>
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
        </div>
      )}
    </div>
  );
}
