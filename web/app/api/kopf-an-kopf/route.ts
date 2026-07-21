import { NextRequest, NextResponse } from "next/server";
import kak from "@/data/kopf_an_kopf.json";

const ERGEBNIS_VOLL: Record<string, string> = { A: "sieg_a", D: "gestellt", B: "sieg_b" };

// Serverseitig gehalten (s. pipeline/export.py:exportiere_kopf_an_kopf) — der
// volle Index ist zu gross für einen Client-Download, darum liefert diese
// Route pro Anfrage nur die Historie EINES Paars zurück. Paar-Schlüssel sind
// numerisch (index[schwinger_id] -> int), daher zuerst die Indizes auflösen.
export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const a = searchParams.get("a");
  const b = searchParams.get("b");
  const daten = kak as unknown as {
    index: Record<string, number>;
    event_index: Record<string, number>;
    paare: Record<string, [number, string][]>;
  };
  if (!a || !b || !(a in daten.index) || !(b in daten.index)) {
    return NextResponse.json({ treffer: [] });
  }
  // Schlüssel folgt derselben Reihenfolge wie beim Export: kanonisch (a < b als String).
  const [kleiner, groesser] = a < b ? [a, b] : [b, a];
  const key = `${daten.index[kleiner]}_${daten.index[groesser]}`;
  const eventIdVon = Object.fromEntries(
    Object.entries(daten.event_index).map(([id, i]) => [i, id])
  );
  const treffer = (daten.paare[key] ?? []).map(([eventIdx, code]) => ({
    event_id: eventIdVon[eventIdx] ?? String(eventIdx),
    ergebnis: ERGEBNIS_VOLL[code] ?? code,
  }));
  return NextResponse.json({ treffer });
}
