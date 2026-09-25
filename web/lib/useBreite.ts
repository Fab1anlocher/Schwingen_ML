"use client";

// Gemessene Breite eines Containers, für SVG-Diagramme: viewBox-Breite =
// Pixelbreite, damit Achsenschrift und Punkte in jeder Spalte und auf dem
// Handy gleich gross bleiben (sonst schrumpfte 11px-Schrift in einer
// schmalen Spalte auf 5-7px oder wuchs auf dem Desktop auf 17px).

import { useCallback, useRef, useState } from "react";

/** [ref, breite]: ``ref`` an das umschliessende Element hängen. ``start`` gilt
 *  bis zur ersten Messung (und beim Vorrendern auf dem Server). Als
 *  Callback-Ref, damit es auch greift, wenn das Element erst später
 *  erscheint (etwa nach dem Laden der Daten). */
export function useBreite(start: number, minimum = 240) {
  const [breite, setBreite] = useState(start);
  const beobachter = useRef<ResizeObserver | null>(null);
  const ref = useCallback(
    (el: HTMLElement | null) => {
      beobachter.current?.disconnect();
      if (!el) return;
      beobachter.current = new ResizeObserver(([e]) =>
        setBreite(Math.max(minimum, Math.round(e.contentRect.width)))
      );
      beobachter.current.observe(el);
    },
    [minimum]
  );
  return [ref, breite] as const;
}
