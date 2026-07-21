"""Zentrale Konfiguration der Pipeline (NFR-3: reproduzierbar, versioniert)."""
from __future__ import annotations

from pathlib import Path

# --- Pfade ---------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
ARTIFACTS_DIR = ROOT / "artifacts"
WEB_PUBLIC_DIR = ROOT / "web" / "public" / "data"
# Serverseitig genutzte Artefakte (NICHT clientseitig geladen, s. web/app/api/).
WEB_SERVER_DATA_DIR = ROOT / "web" / "data"

# --- Reproduzierbarkeit (NFR-3 / AK-6.2) --------------------------------
SEED = 42

# --- Datenschema-Version -------------------------------------------------
SCHEMA_VERSION = "1.0.0"

# --- Modellierung --------------------------------------------------------
# Minimale Anzahl Gänge, ab der eine Prognose ohne Unsicherheitswarnung
# gilt (FR-1 / AK-1.2, konfigurierbar).
MIN_GAENGE_FUER_SICHERHEIT = 5

# Anzahl der letzten Gänge für Form-Merkmal (ML-4).
FORM_FENSTER_K = 5

# Elo-Baseline (ML-2).
ELO_START = 1500.0
ELO_K = 24.0
# Draw-Breite: modelliert P(gestellt) rund um Ratinggleichheit.
ELO_DRAW_WIDTH = 0.30

# Ergebnis-Klassen (ML-1). Reihenfolge ist die Klassen-Indexierung.
KLASSEN = ["sieg_a", "gestellt", "sieg_b"]

# Fest-Typen (§4.2).
FEST_TYPEN = ["eidgenoessisch", "berg", "kantonal", "teilverband", "regional"]

# Höfliches Scraping (NFR-4).
SCRAPE_DELAY_SEKUNDEN = 2.0
USER_AGENT = "Schwingen-ML/1.0 (nicht-kommerziell; Hobby-Projekt)"


def ensure_dirs() -> None:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    WEB_PUBLIC_DIR.mkdir(parents=True, exist_ok=True)
    WEB_SERVER_DATA_DIR.mkdir(parents=True, exist_ok=True)
