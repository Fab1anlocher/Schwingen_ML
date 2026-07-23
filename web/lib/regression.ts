// Einfache lineare Regression (kleinste Quadrate) + Pearson-Korrelation,
// für die Frage "hängt Elo mit Grösse/Gewicht zusammen?" (Analyse-Seite).

export interface RegressionErgebnis {
  steigung: number;
  achsenabschnitt: number;
  r: number; // Pearson-Korrelationskoeffizient, -1..1
}

export function linearRegression(punkte: { x: number; y: number }[]): RegressionErgebnis | null {
  const n = punkte.length;
  if (n < 2) return null;

  const mx = punkte.reduce((s, p) => s + p.x, 0) / n;
  const my = punkte.reduce((s, p) => s + p.y, 0) / n;

  let sxy = 0;
  let sxx = 0;
  let syy = 0;
  for (const { x, y } of punkte) {
    sxy += (x - mx) * (y - my);
    sxx += (x - mx) * (x - mx);
    syy += (y - my) * (y - my);
  }
  if (sxx === 0 || syy === 0) return null;

  const steigung = sxy / sxx;
  const achsenabschnitt = my - steigung * mx;
  const r = sxy / Math.sqrt(sxx * syy);
  return { steigung, achsenabschnitt, r };
}

export function korrelationsStaerke(r: number): string {
  const a = Math.abs(r);
  if (a < 0.1) return "praktisch kein Zusammenhang";
  if (a < 0.3) return "schwacher Zusammenhang";
  if (a < 0.5) return "mittlerer Zusammenhang";
  return "starker Zusammenhang";
}
