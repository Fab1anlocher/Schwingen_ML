"""TEMPORÄR: Status-Spalte der Freiburger Kantonal-Rangliste 2023 vermessen."""
from __future__ import annotations

import collections
import io
import sys

sys.path.insert(0, ".")
from pipeline.scrape.http import hole  # noqa: E402

import pdfplumber  # noqa: E402

url = "https://www.schlussgang.ch/sites/default/files/event-ranking-list/22490-final.pdf"
with pdfplumber.open(io.BytesIO(hole(url, binaer=True))) as pdf:
    for pi, p in enumerate(pdf.pages[:2]):
        zeilen = collections.defaultdict(list)
        for w in p.extract_words():
            zeilen[round(w["top"] / 2.5)].append(w)
        for k in sorted(zeilen)[:40]:
            print(f"p{pi} " + " | ".join(f"{w['text']}@{w['x0']:.0f}" for w in sorted(zeilen[k], key=lambda w: w["x0"])))
