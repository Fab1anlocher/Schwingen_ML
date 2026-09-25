// Fest-Simulation (Monte Carlo): ein ganzes Schwingfest tausendfach
// durchspielen -- Einteilung, Gänge, Noten, Ausstich, Schlussgang, Kränze.
// Zeilengetreue Spiegelung von pipeline/fest_simulation.py (simuliere):
// gleicher Zufallsgenerator (mulberry32), gleiche Reihenfolge der
// Zufallszahlen, gleiche Sortierung -- bei gleichem Feld, gleichen
// Wahrscheinlichkeiten und gleichem Startwert exakt dieselben Zählungen
// (geprüft in der Paritätsprüfung, npm run paritaet). Die Regeln und ihre
// Herkunft stehen in der Python-Datei.

export interface Regeln {
  gaenge: number;
  /** [nach Gang, Anteil, der weiterschwingt] */
  ausstiche: [number, number][];
  /** Anteil der Teilnehmer mit Kranz (üblich 15-18 %). */
  kranzquote: number;
  noten: Noten;
  /** Gang 1: die stärksten so viele (Anteil) nach Elo gegeneinander, der Rest gemischt. */
  anschwingen_anteil: number;
  /** Gang 2..: Punkte + spielraum * Zufall bestimmen die Reihenfolge der Einteilung. */
  spielraum: number;
}

/** Anteil der besseren Note je Ausgang (gemessen 2023-2026, s. Python). */
export interface Noten {
  plattwurf: number;
  aktiv_gestellt: number;
  offensiv_verloren: number;
}

export const NOTEN: Noten = { plattwurf: 0.52, aktiv_gestellt: 0.31, offensiv_verloren: 0.11 };
const FREILOS_NOTE = 9.0;

// Spiegelt REGELN_JE_TYP in pipeline/fest_simulation.py.
const EINTEILUNG = { anschwingen_anteil: 0.2, spielraum: 1.0 };
export const REGELN_JE_TYP: Record<string, Regeln> = {
  kantonal: { gaenge: 6, ausstiche: [[4, 0.8]], kranzquote: 0.16, noten: NOTEN, ...EINTEILUNG },
  teilverband: { gaenge: 6, ausstiche: [[4, 0.8]], kranzquote: 0.16, noten: NOTEN, ...EINTEILUNG },
  berg: { gaenge: 6, ausstiche: [[4, 0.8]], kranzquote: 0.16, noten: NOTEN, ...EINTEILUNG },
  eidgenoessisch: {
    gaenge: 8,
    ausstiche: [
      [4, 0.82],
      [6, 0.55],
    ],
    kranzquote: 0.15,
    noten: NOTEN,
    ...EINTEILUNG,
  },
  regional: { gaenge: 6, ausstiche: [], kranzquote: 0, noten: NOTEN, ...EINTEILUNG },
};

/** Zufallszahlen in [0, 1), bitgleich zu mulberry32 in fest_simulation.py. */
export function mulberry32(seed: number): () => number {
  let a = seed | 0;
  return () => {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export interface SimErgebnis {
  nSim: number;
  festsieg: number[];
  schlussgang: number[];
  kranz: number[];
  punkteSumme: number[];
  kranzgrenzeSumme: number;
}

/** Simuliert ein Fest ``nSim`` Mal. Teilnehmer 0..n-1 in Setzreihenfolge
 *  (stärkster zuerst); pSieg[i][j] = P(i gewinnt gegen j), pGestellt[i][j]
 *  = P(gestellt). */
export function simuliere(
  pSieg: number[][],
  pGestellt: number[][],
  r: Regeln,
  nSim: number,
  seed: number
): SimErgebnis {
  const n = pSieg.length;
  const rng = mulberry32(seed);
  const erg: SimErgebnis = {
    nSim,
    festsieg: new Array(n).fill(0),
    schlussgang: new Array(n).fill(0),
    kranz: new Array(n).fill(0),
    punkteSumme: new Array(n).fill(0),
    kranzgrenzeSumme: 0,
  };
  if (n < 2) return erg;
  const weiterNach = new Map<number, number>(
    r.ausstiche.map(([nach, anteil]) => [nach, Math.ceil(anteil * n)])
  );
  const nKranz = Math.floor(r.kranzquote * n + 0.5);
  const { plattwurf, aktiv_gestellt, offensiv_verloren } = r.noten;

  for (let s = 0; s < nSim; s++) {
    const punkte = new Array<number>(n).fill(0);
    const gegner = Array.from({ length: n }, () => new Set<number>());
    const nachPunkten = (a: number, b: number) => punkte[b] - punkte[a] || a - b;
    let aktiv = Array.from({ length: n }, (_, i) => i);
    let schluss: [number, number, number | null] | null = null;
    for (let gang = 1; gang <= r.gaenge; gang++) {
      const k = weiterNach.get(gang - 1);
      if (k !== undefined && k < aktiv.length) aktiv = [...aktiv].sort(nachPunkten).slice(0, k);
      const istSchlussgang = gang === r.gaenge && aktiv.length >= 2;
      let reihe: number[];
      if (gang === 1) {
        const k = Math.floor(Math.floor(r.anschwingen_anteil * n) / 2) * 2;
        const rest = Array.from({ length: n - k }, (_, x) => k + x);
        for (let a = rest.length - 1; a > 0; a--) {
          // Fisher-Yates
          const b = Math.floor(rng() * (a + 1));
          [rest[a], rest[b]] = [rest[b], rest[a]];
        }
        reihe = [...Array.from({ length: k }, (_, x) => x), ...rest];
      } else {
        const schluessel = new Map<number, number>();
        for (const i of aktiv) schluessel.set(i, punkte[i] + r.spielraum * rng());
        reihe = [...aktiv].sort((a, b) => schluessel.get(b)! - schluessel.get(a)! || a - b);
      }
      const paare: [number, number][] = [];
      if (istSchlussgang) {
        // Der Schlussgang geht an die zwei Punktbesten -- ohne Spielraum.
        const beste = [...aktiv].sort(nachPunkten).slice(0, 2);
        paare.push([beste[0], beste[1]]);
        reihe = reihe.filter((i) => i !== beste[0] && i !== beste[1]);
      }
      const offen = [...reihe];
      while (offen.length >= 2) {
        const i = offen.shift()!;
        const x = offen.findIndex((j) => !gegner[i].has(j));
        paare.push([i, offen.splice(x < 0 ? 0 : x, 1)[0]]);
      }
      if (offen.length) punkte[offen[0]] += FREILOS_NOTE; // ungerade: Freilos
      paare.forEach(([i, j], nr) => {
        const z = rng();
        const pa = pSieg[i][j];
        const pg = pGestellt[i][j];
        const schlussgang = istSchlussgang && nr === 0;
        let sieger: number | null;
        let verlierer: number | null;
        if (z < pa) [sieger, verlierer] = [i, j];
        else if (z < pa + pg) [sieger, verlierer] = [null, null];
        else [sieger, verlierer] = [j, i];
        if (sieger === null) {
          punkte[i] += rng() < aktiv_gestellt ? 9.0 : 8.75;
          punkte[j] += rng() < aktiv_gestellt ? 9.0 : 8.75;
        } else if (schlussgang) {
          punkte[sieger] += 10.0;
          punkte[verlierer!] += 8.75;
        } else {
          punkte[sieger] += rng() < plattwurf ? 10.0 : 9.75;
          punkte[verlierer!] += rng() < offensiv_verloren ? 8.75 : 8.5;
        }
        gegner[i].add(j);
        gegner[j].add(i);
        if (schlussgang) schluss = [i, j, sieger];
      });
    }

    const rang = Array.from({ length: n }, (_, i) => i).sort(nachPunkten);
    let sieger: number;
    if (schluss !== null) {
      const [i, j, s2] = schluss as [number, number, number | null];
      erg.schlussgang[i] += 1;
      erg.schlussgang[j] += 1;
      sieger = s2 !== null ? s2 : rang[0];
    } else {
      sieger = rang[0];
    }
    erg.festsieg[sieger] += 1;
    if (nKranz > 0) {
      const grenze = punkte[rang[nKranz - 1]];
      erg.kranzgrenzeSumme += grenze;
      for (let i = 0; i < n; i++) if (punkte[i] >= grenze) erg.kranz[i] += 1;
    }
    for (let i = 0; i < n; i++) erg.punkteSumme[i] += punkte[i];
  }
  return erg;
}
