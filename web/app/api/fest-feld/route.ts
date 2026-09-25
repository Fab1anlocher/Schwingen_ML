import { NextRequest, NextResponse } from "next/server";
import kak from "@/data/kopf_an_kopf.json";

// Fest-Simulator (app/simulation): das Teilnehmerfeld eines Fests -- alle, die
// dort mindestens einen Gang geschwungen haben -- und die bisherigen Duelle
// JEDES Paars in diesem Feld (für das Kopf-an-Kopf-Merkmal). Wie
// /api/kopf-an-kopf serverseitig, weil der volle Index für den Client zu
// gross ist; Ergebnisse relativ zur kanonisch kleineren ID (a < b).

const ERGEBNIS_VOLL: Record<string, string> = { A: "sieg_a", D: "gestellt", B: "sieg_b" };

interface Index {
  index: Record<string, number>;
  event_index: Record<string, number>;
  paare: Record<string, [number, string][]>;
}

export async function GET(req: NextRequest) {
  const event = new URL(req.url).searchParams.get("event");
  const daten = kak as unknown as Index;
  const festIdx = event ? daten.event_index[event] : undefined;
  if (festIdx === undefined) return NextResponse.json({ teilnehmer: [], paare: [] });

  const idVon = Object.fromEntries(Object.entries(daten.index).map(([id, i]) => [i, id]));
  const eventIdVon = Object.fromEntries(
    Object.entries(daten.event_index).map(([id, i]) => [i, id])
  );
  const imFeld = new Set<string>();
  for (const [paar, duelle] of Object.entries(daten.paare)) {
    if (duelle.some(([f]) => f === festIdx)) {
      const [a, b] = paar.split("_");
      imFeld.add(a);
      imFeld.add(b);
    }
  }
  const paare = Object.entries(daten.paare)
    .filter(([paar]) => {
      const [a, b] = paar.split("_");
      return imFeld.has(a) && imFeld.has(b);
    })
    .map(([paar, duelle]) => {
      const [a, b] = paar.split("_");
      return {
        a: idVon[Number(a)],
        b: idVon[Number(b)],
        treffer: duelle.map(([f, code]) => ({
          event_id: eventIdVon[f] ?? String(f),
          ergebnis: ERGEBNIS_VOLL[code] ?? code,
        })),
      };
    });
  return NextResponse.json({ teilnehmer: [...imFeld].map((i) => idVon[Number(i)]), paare });
}
