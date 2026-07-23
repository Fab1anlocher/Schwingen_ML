"use client";

import { useMemo, useRef, useState } from "react";
import type { Schwinger } from "@/lib/types";

const MAX_ERGEBNISSE = 40;

function normalisiere(s: string): string {
  return s.toLowerCase().normalize("NFKD").replace(/[̀-ͯ]/g, "");
}

function tokens(s: string): string[] {
  return normalisiere(s).trim().split(/\s+/).filter(Boolean);
}

function anzeigeName(s: Schwinger): string {
  return s.jahrgang ? `${s.name} (${s.jahrgang})` : s.name;
}

/**
 * Durchsuchbares Auswahlfeld für Schwinger (ersetzt <select> bei ~2900 Einträgen).
 *
 * `schwinger` sollte vom Aufrufer bereits sinnvoll vorsortiert sein (z.B. nach
 * Elo absteigend) — diese Reihenfolge bestimmt sowohl die Vorschläge bei
 * leerer Suche als auch die Reihenfolge gleichwertiger Treffer.
 * Die Suche selbst ist token-basiert (Reihenfolge "Vorname Nachname" oder
 * "Nachname Vorname" spielt keine Rolle) und scannt IMMER die volle Liste,
 * statt früh abzubrechen — sonst können bei generischen Suchbegriffen
 * frühere Alphabet-Treffer spätere (namentlich eindeutige) Treffer verdecken.
 */
export function SchwingerSuche({
  id,
  label,
  schwinger,
  value,
  onChange,
  hideLabel = false,
}: {
  id: string;
  label: string;
  schwinger: Schwinger[];
  value: string;
  onChange: (id: string) => void;
  hideLabel?: boolean;
}) {
  const [query, setQuery] = useState("");
  const [offen, setOffen] = useState(false);
  const [aktiv, setAktiv] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const ausgewaehlt = schwinger.find((s) => s.id === value) ?? null;

  const treffer = useMemo(() => {
    const qTokens = tokens(query);
    if (qTokens.length === 0) return schwinger.slice(0, MAX_ERGEBNISSE);

    // Rang 0 = exakter Name, 1 = Name beginnt mit dem ersten Token (egal ob
    // Vor- oder Nachname zuerst getippt wurde), 2 = alle Tokens irgendwo
    // enthalten (Name oder Klub/Kantonalverband). Innerhalb eines Rangs
    // bleibt die vom Aufrufer übergebene Reihenfolge erhalten (stable sort).
    const bewertet: { s: Schwinger; rang: number }[] = [];
    for (const s of schwinger) {
      const n = normalisiere(s.name);
      const nTokens = n.split(/\s+/);
      const zusatz = normalisiere([s.schwingklub, s.kanton].filter(Boolean).join(" "));
      const heuhaufen = `${n} ${zusatz}`;
      if (!qTokens.every((t) => heuhaufen.includes(t))) continue;

      let rang = 2;
      if (n === qTokens.join(" ")) rang = 0;
      else if (qTokens.every((t) => nTokens.some((nt) => nt.startsWith(t)))) rang = 1;
      bewertet.push({ s, rang });
    }
    bewertet.sort((a, b) => a.rang - b.rang);
    return bewertet.slice(0, MAX_ERGEBNISSE).map((b) => b.s);
  }, [query, schwinger]);

  const waehle = (s: Schwinger) => {
    onChange(s.id);
    setQuery("");
    setOffen(false);
    inputRef.current?.blur();
  };

  return (
    <div className="such-wrap">
      {!hideLabel && (
        <label className="field" htmlFor={id}>
          {label}
        </label>
      )}
      <input
        ref={inputRef}
        id={id}
        type="text"
        autoComplete="off"
        aria-label={hideLabel ? label : undefined}
        placeholder={ausgewaehlt ? anzeigeName(ausgewaehlt) : "Name suchen …"}
        value={query}
        onFocus={() => setOffen(true)}
        onBlur={() => setOffen(false)}
        onChange={(e) => {
          setQuery(e.target.value);
          setAktiv(0);
          setOffen(true);
        }}
        onKeyDown={(e) => {
          if (!offen) return;
          if (e.key === "ArrowDown") {
            e.preventDefault();
            setAktiv((i) => Math.min(i + 1, treffer.length - 1));
          } else if (e.key === "ArrowUp") {
            e.preventDefault();
            setAktiv((i) => Math.max(i - 1, 0));
          } else if (e.key === "Enter") {
            e.preventDefault();
            if (treffer[aktiv]) waehle(treffer[aktiv]);
          } else if (e.key === "Escape") {
            setOffen(false);
          }
        }}
      />
      {offen && (
        <ul className="such-dropdown" role="listbox">
          {treffer.length === 0 && <li className="such-leer">Keine Treffer</li>}
          {treffer.map((s, i) => (
            <li
              key={s.id}
              role="option"
              aria-selected={s.id === value}
              className={`such-option${i === aktiv ? " such-option-aktiv" : ""}${
                s.id === value ? " such-option-gewaehlt" : ""
              }`}
              onMouseDown={(e) => {
                e.preventDefault();
                waehle(s);
              }}
              onMouseEnter={() => setAktiv(i)}
            >
              <span>{anzeigeName(s)}</span>
              <span className="such-meta">
                {[s.schwingklub, s.kanton].filter(Boolean).join(" · ")}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
