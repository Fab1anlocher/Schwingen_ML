// Paritätsprüfung TypeScript <-> Python (Gegenstück zu pipeline/paritaet.py).
//
// Rechnet die von Python erzeugten Prüffälle mit den kompilierten
// TypeScript-Modulen der App nach und bricht ab, sobald eine Zahl abweicht.
// Aufruf über `npm run paritaet` (kompiliert vorher nach .paritaet/).
//
// Geprüft wird dreierlei, bewusst getrennt, damit ein Fehler dort gemeldet
// wird, wo er entsteht:
//   1. Kopf-an-Kopf-Vorteil inkl. Richtungsumkehr (kopfAnKopf.ts)
//   2. Merkmalsvektor, mit PYTHONS Kopf-an-Kopf als Eingabe (baueFeatures)
//   3. Wahrscheinlichkeiten Ende-zu-Ende, genau wie die App sie berechnet

const fs = require("fs");
const path = require("path");

const BUILD = path.resolve(__dirname, "../.paritaet");
const { baueFeatures, prognostiziere } = require(path.join(BUILD, "inference.js"));
const { kopfAnKopfVorteilA, trefferAusSichtVonA } = require(path.join(BUILD, "kopfAnKopf.js"));

const datei = process.argv[2] || path.join(BUILD, "faelle.json");
const { model, model_v1: modelV1, jahr, faelle } = JSON.parse(fs.readFileSync(datei, "utf8"));

// Relativ, weil Python und V8 bei exp/log1p im letzten Bit abweichen dürfen.
const TOL = 1e-9;
const gleich = (a, b) => Math.abs(a - b) <= TOL * Math.max(1, Math.abs(a), Math.abs(b));

if (jahr !== new Date().getFullYear()) {
  console.warn(`Hinweis: Fälle für ${jahr} erzeugt, heute ist ${new Date().getFullYear()} (Alter kann abweichen).`);
}

const fehler = [];
const proGruppe = {};
let maxMerkmal = 0;
let maxWahrsch = 0;

for (const f of faelle) {
  const g = (proGruppe[f.gruppe] = proGruppe[f.gruppe] || { n: 0, fehler: 0 });
  g.n++;
  const kennung = `${f.gruppe}: ${f.a.id} vs ${f.b.id}`;
  const vorher = fehler.length;
  // Gruppe "modell-v1": dieselbe App gegen ein model.json älterer Version --
  // sie muss dann nach DESSEN Merkmalsdefinition rechnen.
  const m = f.modell === "v1" ? modelV1 : model;

  // 1. Kopf-an-Kopf
  const h2hTs = kopfAnKopfVorteilA(trefferAusSichtVonA(f.treffer_kanonisch, f.a.id, f.b.id));
  if (!gleich(h2hTs, f.erwartet.h2h)) {
    fehler.push(`${kennung} | Kopf-an-Kopf TS ${h2hTs} ≠ Python ${f.erwartet.h2h}`);
  }

  // 2. Merkmalsvektor, isoliert
  const x = baueFeatures(m, f.a, f.b, f.rating_a.elo, f.rating_b.elo,
    f.rating_a.n_gaenge, f.rating_b.n_gaenge, f.erwartet.h2h);
  if (x.length !== f.erwartet.merkmale.length) {
    fehler.push(`${kennung} | ${x.length} Merkmale in TS, ${f.erwartet.merkmale.length} in Python ` +
      `— ein Merkmal fehlt auf einer Seite`);
  } else {
    x.forEach((v, i) => {
      const d = Math.abs(v - f.erwartet.merkmale[i]);
      if (Number.isFinite(d)) maxMerkmal = Math.max(maxMerkmal, d);
      if (!gleich(v, f.erwartet.merkmale[i])) {
        const name = m.features[i] ?? `Merkmal #${i} (nicht im ausgelieferten Modell)`;
        fehler.push(`${kennung} | ${name}: TS ${v} ≠ Python ${f.erwartet.merkmale[i]}`);
      }
    });
  }

  // 3. Wahrscheinlichkeiten Ende-zu-Ende
  const prognose = prognostiziere(m, f.a, f.b, f.rating_a.elo, f.rating_b.elo,
    f.rating_a.n_gaenge, f.rating_b.n_gaenge, h2hTs);
  const p = prognose.p;
  m.klassen.forEach((kl, k) => {
    const d = Math.abs(p[kl] - f.erwartet.wahrscheinlichkeiten[k]);
    if (Number.isFinite(d)) maxWahrsch = Math.max(maxWahrsch, d);
    if (!gleich(p[kl], f.erwartet.wahrscheinlichkeiten[k])) {
      fehler.push(`${kennung} | P(${kl}) TS ${p[kl]} ≠ Python ${f.erwartet.wahrscheinlichkeiten[k]}`);
    }
  });

  // 4. Erklärung: endlich, und nie ein Merkmal, das niemanden bevorzugen kann,
  //    einem Schwinger gutgeschrieben (s. SYMMETRISCH in inference.ts).
  for (const b of prognose.beitraege) {
    if (!Number.isFinite(b.staerke) || !Number.isFinite(b.veraenderung)) {
      fehler.push(`${kennung} | Beitrag „${b.titel}“ nicht endlich`);
    }
    if (["Ausgeglichenheit", "Teilverband", "Ähnlicher Stil", "Gestellt-Neigung"].includes(b.titel) &&
        b.richtung !== "gestellt") {
      fehler.push(`${kennung} | „${b.titel}“ bevorzugt niemanden, steht aber bei ${b.richtung}`);
    }
  }

  if (fehler.length > vorher) g.fehler++;
}

console.log(`Parität TypeScript ↔ Python: ${faelle.length} Fälle, Modell mit ${model.features.length} Merkmalen ` +
  `(Merkmalsversion ${model.config.merkmal_version ?? 1})`);
for (const [gruppe, { n, fehler: fe }] of Object.entries(proGruppe).sort()) {
  console.log(`  ${gruppe.padEnd(20)} ${String(n).padStart(3)} Fälle  ${fe ? `✗ ${fe} abweichend` : "✓"}`);
}
console.log(`  max. Abweichung Merkmale ${maxMerkmal.toExponential(2)}, Wahrscheinlichkeiten ${maxWahrsch.toExponential(2)}`);

if (fehler.length) {
  console.error(`\n✗ ${fehler.length} Abweichung(en) — die App rechnet anders als das Modell:`);
  fehler.slice(0, 25).forEach((z) => console.error("  " + z));
  if (fehler.length > 25) console.error(`  … und ${fehler.length - 25} weitere`);
  process.exit(1);
}
console.log("✓ Die App rechnet identisch zur Pipeline.");
