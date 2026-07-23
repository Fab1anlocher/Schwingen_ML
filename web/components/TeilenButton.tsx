"use client";

import { useState } from "react";

/** Kopiert die aktuelle URL (die Prognose-Seite hält ?a=&b= laufend synchron,
 * daher teilt dieser Button immer den gerade sichtbaren Vergleich). */
export function TeilenButton() {
  const [kopiert, setKopiert] = useState(false);
  return (
    <button
      type="button"
      className={`teilen-btn${kopiert ? " teilen-kopiert" : ""}`}
      title="Link zu dieser Seite kopieren"
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
      {kopiert ? "✓ Kopiert" : "Link teilen"}
    </button>
  );
}
