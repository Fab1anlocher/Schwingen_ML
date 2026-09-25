"""Wertet npm audit und pip-audit aus (Workflow .github/workflows/sicherheit.yml).

Ersatz für die Dependabot-Sicherheitsupdates, die nur in den Repo-
Einstellungen einzuschalten sind: der geplante Lauf meldet bekannte
Schwachstellen als Issue und schliesst es wieder, sobald sie behoben sind.

Aufruf: python scripts/sicherheitsbericht.py npm-audit.json pip-audit.json bericht.md
Exit-Code 1, wenn es Befunde gibt (dann schlägt der Lauf fehl und GitHub
benachrichtigt zusätzlich per Mail).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Ab dieser Stufe zählt ein npm-Befund. Gleiche Schwelle wie der CI-Job
# abhaengigkeiten-audit (darunter vor allem Build-Werkzeuge ohne Angriffsfläche).
NPM_STUFEN = ("high", "critical")


def _lade(pfad: str) -> dict | None:
    try:
        return json.loads(Path(pfad).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def npm_befunde(audit: dict | None) -> list[str]:
    """Zeilen je verwundbarem Paket (Web-App, nur Laufzeit-Abhängigkeiten)."""
    if audit is None:
        return ["npm audit lieferte kein auswertbares Ergebnis"]
    zeilen = []
    for name, v in sorted((audit.get("vulnerabilities") or {}).items()):
        if v.get("severity") not in NPM_STUFEN:
            continue
        titel = [x.get("title") for x in v.get("via", []) if isinstance(x, dict) and x.get("title")]
        fix = v.get("fixAvailable")
        fix_text = "Fix verfügbar" if fix else "noch kein Fix"
        if isinstance(fix, dict) and fix.get("name"):
            fix_text = f"Fix: {fix['name']} {fix.get('version', '')}".strip()
        zeilen.append(f"- **{name}** ({v.get('severity')}, {v.get('range', '?')}): "
                      f"{'; '.join(titel[:3]) or 'über Abhängigkeit'} — {fix_text}")
    return zeilen


def pip_befunde(audit: dict | None) -> list[str]:
    """Zeilen je verwundbarem Paket (Pipeline)."""
    if audit is None:
        return ["pip-audit lieferte kein auswertbares Ergebnis"]
    zeilen = []
    for dep in audit.get("dependencies") or []:
        for vuln in dep.get("vulns") or []:
            fix = ", ".join(vuln.get("fix_versions") or []) or "noch kein Fix"
            zeilen.append(f"- **{dep.get('name')} {dep.get('version')}**: {vuln.get('id')} — Fix: {fix}")
    return zeilen


def bericht(npm: list[str], pip: list[str]) -> str:
    teile = ["Automatischer Bericht des Workflows **Sicherheits-Audit** "
             "(`.github/workflows/sicherheit.yml`).", ""]
    teile += ["### Web-App (npm, Laufzeit-Abhängigkeiten, ab high)", ""]
    teile += npm or ["- keine Befunde"]
    teile += ["", "### Pipeline (pip)", ""]
    teile += pip or ["- keine Befunde"]
    teile += ["", "Beheben: Abhängigkeit auf die Fix-Version heben (Web: `npm install <paket>@<version>` "
              "bzw. `overrides` in `web/package.json`; Pipeline: Mindestversion in "
              "`requirements-pipeline.txt`). Das Issue schliesst sich beim nächsten "
              "Lauf ohne Befund von selbst."]
    return "\n".join(teile)


def main(argv: list[str]) -> int:
    npm_pfad, pip_pfad, ziel = argv
    npm = npm_befunde(_lade(npm_pfad))
    pip = pip_befunde(_lade(pip_pfad))
    Path(ziel).write_text(bericht(npm, pip), encoding="utf-8")
    print(f"{len(npm)} npm-Befunde, {len(pip)} pip-Befunde")
    return 1 if npm or pip else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
