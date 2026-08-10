"""Zentrale Konfiguration der Pipeline (NFR-3: reproduzierbar, versioniert)."""
from __future__ import annotations

from pathlib import Path

# --- Pfade ---------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
ARTIFACTS_DIR = ROOT / "artifacts"
WEB_PUBLIC_DIR = ROOT / "web" / "public" / "data"

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

# Höfliches Scraping (NFR-4): Rate-Limit + robots.txt bleiben aktiv. Der
# User-Agent ist browser-kompatibel, weil esv.ch nicht-Browser-UAs mit 403
# blockt; die Kennung „Schwingen-ML" bleibt zur Transparenz enthalten.
SCRAPE_DELAY_SEKUNDEN = 2.0
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36 Schwingen-ML/1.0 (nicht-kommerziell)"
)

# --- Datenquelle: ESV (esv.ch/ranglisten) -------------------------------
# Offizielle Ranglisten des Eidgenössischen Schwingerverbands.
# Einzelfest-Rangliste: <ESV_BASE>?anlass=<ID>
ESV_BASE = "https://esv.ch/ranglisten/"
# Regionale Subdomains fahren dasselbe System (nur andere Vorauswahl);
# esv.ch selbst liefert alle Anlässe.
ESV_REGIONEN = ["esv", "isv", "nosv", "bksv", "nwsv", "swsv", "zksv"]
QUELLE = "esv.ch"


def ensure_dirs() -> None:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    WEB_PUBLIC_DIR.mkdir(parents=True, exist_ok=True)
