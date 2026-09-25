"""Einmalig: report_verlauf.json aus der Git-Historie von artifacts/report.json.

Der Verlauf der Modellgüte (T1) wird seit dem 26.09.2026 bei jedem
Pipeline-Lauf fortgeschrieben (export.ergaenze_verlauf). Die Läufe davor
stehen nur in der Git-Historie des Bot-Commits -- dieses Skript liest sie
aus, damit der Verlauf nicht leer beginnt. Je Tag und Modellstand zählt
der letzte Lauf (wie export.ergaenze_verlauf).

Aufruf (vollständige Historie nötig, kein flacher Klon):
    git fetch --unshallow origin
    python scripts/verlauf_aus_git.py
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline.export import verlauf_eintrag, verlauf_schluessel  # noqa: E402


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, text=True).stdout


def main() -> int:
    je_stand: dict[tuple, dict] = {}
    for zeile in _git("log", "--reverse", "--format=%H %ad", "--date=short", "--", "artifacts/report.json").splitlines():
        sha, datum = zeile.split()
        try:
            report = json.loads(_git("show", f"{sha}:artifacts/report.json"))
        except (subprocess.CalledProcessError, json.JSONDecodeError):
            continue
        if report.get("modell", {}).get("log_loss") is None:
            continue
        if ((report.get("datenbasis") or {}).get("n_gaenge") or 0) < 20000:
            continue  # Test- und Demodaten-Läufe beim Aufbau (20.07.2026: 2 bzw. 2706 Gänge)
        eintrag = verlauf_eintrag(report)
        eintrag["datum"] = datum  # Commit-Datum; ältere Reports haben kein "erstellt"
        je_stand.pop(verlauf_schluessel(eintrag), None)  # der letzte Lauf gewinnt, ...
        je_stand[verlauf_schluessel(eintrag)] = eintrag  # ... an seiner Stelle der Reihenfolge
    laeufe = sorted(je_stand.values(), key=lambda l: l["datum"])
    ziel = {"schema_version": "1.0.0", "laeufe": laeufe}
    for pfad in (ROOT / "artifacts" / "report_verlauf.json", ROOT / "web" / "public" / "data" / "report_verlauf.json"):
        pfad.write_text(json.dumps(ziel, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(laeufe)} Einträge, {laeufe[0]['datum']} .. {laeufe[-1]['datum']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
