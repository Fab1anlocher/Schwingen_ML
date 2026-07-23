"use client";

import { useEffect, useMemo, useState } from "react";
import { ladeEvents, ladeModel, ladeRatings, ladeSchwinger } from "@/lib/data";
import { prognostiziere } from "@/lib/inference";
import type { ModelArtifact, RatingsArtifact, Schwinger, Prognose } from "@/lib/types";
import { PrognoseView } from "@/components/PrognoseView";
import { SchwingerSuche } from "@/components/SchwingerSuche";
import { KopfAnKopf } from "@/components/KopfAnKopf";
import { ladeKopfAnKopf, kopfAnKopfVorteilA, type H2HTreffer } from "@/lib/kopfAnKopf";

export default function Home() {
  const [model, setModel] = useState<ModelArtifact | null>(null);
  const [ratings, setRatings] = useState<RatingsArtifact | null>(null);
  const [schwinger, setSchwinger] = useState<Schwinger[]>([]);
  const [aId, setAId] = useState("");
  const [bId, setBId] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [eventInfo, setEventInfo] = useState<Record<string, { name: string; datum: string }>>({});
  const [h2hTreffer, setH2hTreffer] = useState<H2HTreffer[] | null>(null);

  useEffect(() => {
    Promise.all([ladeModel(), ladeRatings(), ladeSchwinger()])
      .then(([m, r, s]) => {
        setModel(m);
        setRatings(r);
        // Nach Elo absteigend: bekannteste/staerkste Schwinger zuerst — sowohl
        // als Vorschlag bei leerer Suche als auch als Default-Paarung.
        const sortiert = [...s].sort(
          (a, b) => (r.ratings[b.id]?.elo ?? r.elo_start) - (r.ratings[a.id]?.elo ?? r.elo_start)
        );
        setSchwinger(sortiert);
        // Aus geteiltem Link übernehmen (?a=...&b=...), sonst Top 2 als Default.
        const params = new URLSearchParams(window.location.search);
        const vorhandeneIds = new Set(sortiert.map((sw) => sw.id));
        const aAusUrl = params.get("a");
        const bAusUrl = params.get("b");
        setAId(aAusUrl && vorhandeneIds.has(aAusUrl) ? aAusUrl : sortiert[0]?.id ?? "");
        setBId(
          bAusUrl && vorhandeneIds.has(bAusUrl)
            ? bAusUrl
            : sortiert[1]?.id && sortiert[1].id !== aAusUrl
            ? sortiert[1].id
            : sortiert[0]?.id ?? ""
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

  // Kopf-an-Kopf-Historie laden — fliesst als Merkmal in die Prognose UND
  // in die Anzeige ein (einmal laden, beides speisen statt doppelt fetchen).
  useEffect(() => {
    if (!aId || !bId || aId === bId) {
      setH2hTreffer(null);
      return;
    }
    let aktuell = true;
    setH2hTreffer(null);
    ladeKopfAnKopf(aId, bId)
      .then((t) => aktuell && setH2hTreffer(t))
      .catch(() => aktuell && setH2hTreffer([]));
    return () => {
      aktuell = false;
    };
  }, [aId, bId]);

  const h2hVorteilA = useMemo(
    () => (h2hTreffer ? kopfAnKopfVorteilA(h2hTreffer) : 0),
    [h2hTreffer]
  );

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
    return prognostiziere(model, a, b, eloA, eloB, nA, nB, h2hVorteilA);
  }, [model, eingaben, h2hVorteilA]);

  if (error) return <p className="warn">Fehler beim Laden: {error}</p>;
  if (!model) return <p className="loading">Modell wird geladen …</p>;

  const a = byId[aId];
  const b = byId[bId];

  return (
    <div>
      <span className="eyebrow">Paar-Prognose</span>
      <h1>Wer schwingt obenaus?</h1>
      <p className="subtitle">
        Zwei Schwinger wählen — das Modell schätzt Sieg A, Gestellt und Sieg B, und legt offen,
        welche Merkmale den Ausschlag geben.
      </p>

      <hr className="rule" />

      <div className="auswahl">
        <div className="auswahl-zelle">
          <div className="auswahl-label">
            <span className="auswahl-marker auswahl-marker-a" />
            Schwinger A
          </div>
          <SchwingerSuche id="a" label="Schwinger A" schwinger={schwinger} value={aId} onChange={setAId} hideLabel />
          <div className="auswahl-meta">{metaZeile(a)}</div>
        </div>
        <div className="auswahl-swap">
          <button
            type="button"
            className="swap-btn"
            title="Schwinger A und B tauschen"
            aria-label="Schwinger A und B tauschen"
            onClick={() => {
              setAId(bId);
              setBId(aId);
            }}
          >
            ⇄
          </button>
        </div>
        <div className="auswahl-zelle">
          <div className="auswahl-label">
            <span className="auswahl-marker auswahl-marker-b" />
            Schwinger B
          </div>
          <SchwingerSuche id="b" label="Schwinger B" schwinger={schwinger} value={bId} onChange={setBId} hideLabel />
          <div className="auswahl-meta">{metaZeile(b)}</div>
        </div>
      </div>

      {aId === bId && (
        <div className="warn" style={{ marginTop: "1rem" }}>
          Bitte zwei unterschiedliche Schwinger wählen.
        </div>
      )}

      {prognose && eingaben && (
        <>
          <div className="vs-banner">
            <div className="vs-seite vs-seite-a">
              <div className="vs-rolle">Schwinger A</div>
              <div className="vs-name">{eingaben.a.name}</div>
              <div className="vs-meta">
                {eingaben.a.teilverband ?? "—"} · Elo {Math.round(eingaben.eloA)}
              </div>
            </div>
            <div className="vs-mitte">vs</div>
            <div className="vs-seite vs-seite-b">
              <div className="vs-rolle">Schwinger B</div>
              <div className="vs-name">{eingaben.b.name}</div>
              <div className="vs-meta">
                {eingaben.b.teilverband ?? "—"} · Elo {Math.round(eingaben.eloB)}
              </div>
            </div>
          </div>

          <PrognoseView prognose={prognose} nameA={eingaben.a.name} nameB={eingaben.b.name} />

          <h2>Kopf an Kopf</h2>
          <KopfAnKopf
            treffer={h2hTreffer}
            nameA={eingaben.a.name}
            nameB={eingaben.b.name}
            eventInfo={eventInfo}
          />
        </>
      )}
    </div>
  );
}

/** Kurze Metazeile unter dem Auswahlfeld: Teilverband · Jahrgang · Kränze. */
function metaZeile(s: Schwinger | undefined): string {
  if (!s) return "";
  const teile: string[] = [];
  if (s.teilverband) teile.push(s.teilverband);
  if (s.jahrgang) teile.push(`Jg. ${s.jahrgang}`);
  if (s.anzahl_kraenze > 0)
    teile.push(`${s.anzahl_kraenze} Kranz${s.anzahl_kraenze === 1 ? "" : "gewinne"}`);
  return teile.join(" · ");
}
