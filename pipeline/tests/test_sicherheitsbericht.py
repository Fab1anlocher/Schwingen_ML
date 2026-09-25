"""scripts/sicherheitsbericht.py: Ersatz für die Dependabot-Sicherheitsupdates."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

_PFAD = Path(__file__).resolve().parents[2] / "scripts" / "sicherheitsbericht.py"
_spec = importlib.util.spec_from_file_location("sicherheitsbericht", _PFAD)
sb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sb)


def _npm(**pakete):
    return {"vulnerabilities": {
        name: {"severity": stufe, "range": "<9", "via": [{"title": f"Lücke in {name}"}],
               "fixAvailable": {"name": name, "version": "9.0.0"}}
        for name, stufe in pakete.items()}}


def test_npm_zaehlt_erst_ab_high():
    assert sb.npm_befunde(_npm(postcss="moderate", lodash="low")) == []
    zeilen = sb.npm_befunde(_npm(next="critical", axios="high"))
    assert len(zeilen) == 2 and "next" in zeilen[1] and "Fix: next 9.0.0" in zeilen[1]


def test_pip_befund_mit_fix_version():
    audit = {"dependencies": [{"name": "pdfminer-six", "version": "1", "vulns": [
        {"id": "GHSA-1", "fix_versions": ["2"]}]}, {"name": "numpy", "version": "2", "vulns": []}]}
    assert sb.pip_befunde(audit) == ["- **pdfminer-six 1**: GHSA-1 — Fix: 2"]


def test_fehlendes_ergebnis_ist_ein_befund():
    """Ein kaputter Audit-Lauf darf nicht als "alles sauber" durchgehen."""
    assert sb.npm_befunde(None) and sb.pip_befunde(None)


def test_exit_code_und_bericht(tmp_path):
    (tmp_path / "npm.json").write_text(json.dumps(_npm(postcss="moderate")))
    (tmp_path / "pip.json").write_text(json.dumps({"dependencies": []}))
    assert sb.main([str(tmp_path / "npm.json"), str(tmp_path / "pip.json"), str(tmp_path / "b.md")]) == 0
    (tmp_path / "npm.json").write_text(json.dumps(_npm(next="critical")))
    assert sb.main([str(tmp_path / "npm.json"), str(tmp_path / "pip.json"), str(tmp_path / "b.md")]) == 1
    assert "next" in (tmp_path / "b.md").read_text()
