// Teilnehmerkreis eines Fests aus seinem Namen ableiten — FALLBACK.
//
// Massgeblich ist `KommendesFest.teilverband` aus dem Artefakt: die Pipeline
// bestimmt den Kreis aus den Teilnehmern der Vorausgabe desselben Fests
// (pipeline/teilnehmerkreis.py) und deckt damit auch Regionalfeste ab, deren
// Name nur einen Ort nennt ("Herbstschwinget Unteriberg"). Diese Muster
// greifen nur bei Artefakten, die das Feld noch nicht führen.
//
// Warum das nötig ist: an Teilverbands- und Kantonalfesten startet fast
// ausschliesslich, wer dem betreffenden Verband angehört. Gemessen an den
// erfassten Festen 2023–2026:
//
//   Teilverbandsfeste  79–94 % der Teilnehmer aus dem eigenen Teilverband
//   Kantonalfeste      85–97 % aus einem dominierenden Teilverband
//   Bergfeste          33–55 % — offenes, gesamtschweizerisches Feld
//
// Eine Favoritenliste ohne diesen Filter zeigt an einem Nordwestschweizer
// Schwingfest die national stärksten Schwinger, von denen dort keiner antritt.
//
// Die Muster bilden die offizielle ESV-Gliederung ab (5 Teilverbände,
// 29 Kantonal-/Gauverbände) — dieselbe Quelle wie `pipeline/kantone.py`.
// Gegen alle 120 erfassten Kantonal- und Teilverbandsfeste validiert:
// 120/120 richtig, 0 Falschtreffer bei Berg-/Eidgenössischen Festen
// (`pipeline/tests/test_teilverband_zuordnung.py` hält das fest).
//
// Wortgrenzen sind zwingend: ohne sie steckt "urner" in "Solothurner" und
// ein Nordwestschweizer Fest gilt als Innerschweizer.

export const TEILVERBAND_MUSTER: [string, RegExp][] = [
  [
    "Bern",
    /\b(bern-jurassisch\w*|berner|emmentalisch\w*|mittelländisch\w*|oberaargauisch\w*|seeländisch\w*|oberländisch\w*)\b/,
  ],
  [
    "Innerschweiz",
    /\b(innerschweizer|luzerner|ob-\s*und\s*nidwaldner|obwaldner|nidwaldner|schwyzer|urner|zuger|tessiner)\b/,
  ],
  [
    "Nordostschweiz",
    /\b(nordostschweizer|appenzeller|glarner|bündner|schaffhauser|st\.\s*galler|thurgauer|toggenburger|zürcher)\b/,
  ],
  [
    "Nordwestschweiz",
    /\b(nordwestschweizer|aargauer|baselbieter|baselstädtisch\w*|baselland\w*|solothurner)\b/,
  ],
  [
    "Suedwestschweiz",
    /\b(südwestschweizer|freiburger|fribourgeois\w*|genfer|jurassisch\w*|neuenburger|waadtländer|walliser|vaudois\w*|valaisan\w*)\b/,
  ],
];

/** Teilverband, dessen Schwinger an diesem Fest starten — oder null bei
 *  offenem Feld (Berg-/Eidgenössische Feste) bzw. unbekannter Zuordnung. */
export function teilverbandFuerFest(name: string, typ: string): string | null {
  if (typ !== "teilverband" && typ !== "kantonal") return null;
  const n = name.toLowerCase();
  for (const [teilverband, muster] of TEILVERBAND_MUSTER) {
    if (muster.test(n)) return teilverband;
  }
  return null;
}
