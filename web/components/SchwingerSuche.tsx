"use client";

import { useMemo, useRef, useState } from "react";
import type { Schwinger } from "@/lib/types";

const MAX_ERGEBNISSE = 40;

function normalisiere(s: string): string {
  return s.toLowerCase().normalize("NFKD").replace(/[̀-ͯ]/g, "");
}

function anzeigeName(s: Schwinger): string {
  return s.jahrgang ? `${s.name} (${s.jahrgang})` : s.name;
}

/** Durchsuchbares Auswahlfeld für Schwinger (ersetzt <select> bei ~2900 Einträgen). */
export function SchwingerSuche({
  id,
  label,
  schwinger,
  value,
  onChange,
}: {
  id: string;
  label: string;
  schwinger: Schwinger[];
  value: string;
  onChange: (id: string) => void;
}) {
  const [query, setQuery] = useState("");
  const [offen, setOffen] = useState(false);
  const [aktiv, setAktiv] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  const ausgewaehlt = schwinger.find((s) => s.id === value) ?? null;

  const treffer = useMemo(() => {
    const q = normalisiere(query.trim());
    if (!q) return schwinger.slice(0, MAX_ERGEBNISSE);
    const startet: Schwinger[] = [];
    const enthaelt: Schwinger[] = [];
    for (const s of schwinger) {
      const n = normalisiere(s.name);
      if (n.startsWith(q)) startet.push(s);
      else if (
        n.includes(q) ||
        normalisiere(s.schwingklub ?? "").includes(q) ||
        normalisiere(s.kanton ?? "").includes(q)
      )
        enthaelt.push(s);
      if (startet.length + enthaelt.length >= MAX_ERGEBNISSE * 3) break;
    }
    return [...startet, ...enthaelt].slice(0, MAX_ERGEBNISSE);
  }, [query, schwinger]);

  const waehle = (s: Schwinger) => {
    onChange(s.id);
    setQuery("");
    setOffen(false);
    inputRef.current?.blur();
  };

  return (
    <div className="such-wrap">
      <label className="field" htmlFor={id}>
        {label}
      </label>
      <input
        ref={inputRef}
        id={id}
        type="text"
        autoComplete="off"
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
