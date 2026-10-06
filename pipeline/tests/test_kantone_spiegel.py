"""web/lib/kantone.ts spiegelt pipeline/kantone.py (Karte: Steckbrief und
Duell zählen dieselben Schwinger wie kantone.json) -- beide Tabellen gleich."""
from __future__ import annotations

import re
from pathlib import Path

from pipeline.kantone import KANTONALVERBAND_ZU_KANTON

TS = Path(__file__).resolve().parents[2] / "web" / "lib" / "kantone.ts"


def test_typescript_tabelle_gleich_python():
    text = TS.read_text(encoding="utf-8")
    block = text[text.index("KANTONALVERBAND_ZU_KANTON"):]
    block = block[block.index("{") + 1:block.index("};")]
    ts = {}
    for schluessel, werte in re.findall(r'^\s*"?([^":\n]+?)"?:\s*\[([^\]]*)\]', block, re.M):
        ts[schluessel.strip()] = re.findall(r'"([^"]+)"', werte)
    assert ts == KANTONALVERBAND_ZU_KANTON
