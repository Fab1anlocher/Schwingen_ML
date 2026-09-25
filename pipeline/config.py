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

# --- Merkmalsdefinition (P3) --------------------------------------------
# Version der Merkmalsdefinition. Steht in model.json; die App rechnet ein
# älteres ausgeliefertes Modell mit DESSEN Definition weiter (inference.ts),
# damit ein Modell, das dem Code einen Lauf hinterherhinkt, richtig rechnet.
#   1: Elo-Abstand / 100, Erfahrung als rohe Differenz der Gangzahlen
#   2: Elo-Abstand / aktuelle Streuung, Erfahrung logarithmisch,
#      + Gestellt-Neigung
#      Gemessen an echten Daten (Validierung 2025 und Test 2026 gleichsinnig):
#      Test-Log-Loss 0.8314 -> 0.7503, Accuracy 63.9 % -> 68.2 %.
#   3: + Gestellt-Bilanz des Paars, + Spitzen-Niveau (s. features.py).
#      Version 2 unterschätzte Gestellt genau dort, wo man hinschaut: in den
#      Spitzenpaarungen (oberstes 1 % nach Stärke, Test 2026: 18.2 %
#      vorhergesagt, 29.7 % eingetreten) und bei Paaren, die schon oft
#      gestellt haben (>= 2 Duelle, davon >= die Hälfte gestellt: 32.5 % zu
#      42.1 %). Mit Version 3: 29.6 % bzw. 40.1 %; Log-Loss Validierung 2025
#      0.7771 -> 0.7757, Test 2026 0.7503 -> 0.7491.
MERKMAL_VERSION = 3

# --- Modelltyp (Roadmap M1, s. modell.py) ------------------------------
# "gbm" = zweistufiges Gradient Boosting (P(Gestellt), dann P(Sieg A |
# entschieden)), "lr" = Logistic Regression (bis 25.09.2026; bleibt als
# Rückfall und im Benchmark). Gemessen mit denselben Merkmalen: Log-Loss
# Validierung 2025 0.7627 -> 0.7400, Test 2026 0.7400 -> 0.7207.
MODELL_TYP = "gbm"
# Baumzahl je Stufe: bis zu GBM_MAX_BAEUME, gewählt auf den jüngsten
# VALIDIERUNGSANTEIL der Trainingsdaten (zeitlich, nicht zufällig).
GBM_MAX_BAEUME = 800
GBM_LERNRATE = 0.1
GBM_MAX_BLAETTER = 15
# Mindestens so viele Trainingszeilen je Blatt. Die Gestellt-Stufe braucht
# mehr (100 statt 40: Validierung 0.7406 -> 0.7398, Test 0.7213 -> 0.7211);
# Lernrate 0.05 mit 31 Blättern war nicht besser (0.7414 / 0.7207).
GBM_MIN_BLATT_GESTELLT = 100
GBM_MIN_BLATT_SIEG = 40
# Monotonie-Vorgaben je Stufe: +1 = steigt das Merkmal, darf die
# Wahrscheinlichkeit nicht sinken; -1 = nicht steigen. Nur wo die Richtung
# sachlich feststeht. Ohne sie senkte bei 6-15 % der Paare eine höhere
# Gestellt-Bilanz oder ein kleinerer Rating-Abstand die Gestellt-Chance
# (Erklärbalken dann unsinnig); mit ihnen 0 %, Log-Loss gleich (+-0.0004).
# Mehr Vorgaben (Form, Kranz, Erfahrung) kosteten 0.005-0.007.
MONOTON_GESTELLT = {"paar_gestellt": 1, "gestellt_neigung": 1, "rating_abstand": -1}
MONOTON_SIEG = {"rating_diff": 1, "kopf_an_kopf": 1}
VALIDIERUNGSANTEIL = 0.15

# Gestellt-Bilanz eines Paars: Anteil gestellter Duelle, geschrumpft gegen die
# Erwartung aus den beiden Einzelneigungen mit so vielen "Phantom-Duellen".
# K = 2, 4, 8, 16 lagen auf Validierung und Test gleichauf (+-0.0001); 4 heisst:
# nach vier Duellen zählt die eigene Bilanz so viel wie die Erwartung.
PAAR_GESTELLT_K = 4.0

# Gestellt-Neigung je Schwinger: Anteil gestellter Gänge, geschrumpft gegen
# den Gesamtdurchschnitt mit so vielen "Phantom-Gängen". Die Neigung ist eine
# stabile Eigenschaft (erste gegen zweite Karrierehälfte: r = 0.67, Spanne
# 0-63 %). Log-Loss zwischen K=10 und K=40 flach; 20 liegt in der Mitte.
GESTELLT_NEIGUNG_K = 20.0

# Streuung der Elo-Ratings, in deren Einheiten der Elo-Abstand gemessen wird.
# Die Ratings driften auseinander, solange das System einschwingt (Streuung
# der aktiven Ratings 2023: 41, 2024: 77, 2025: 107, 2026: 126) -- derselbe
# echte Stärkeunterschied bekäme sonst jedes Jahr mehr Punkte, und das Modell
# hielte 2026 jede Paarung für einseitiger, als sie ist: ohne Skalierung
# 18.3 % Gestellt vorhergesagt bei 21.1 % eingetreten, mit ihr 20.5 %
# (Test-Log-Loss 0.7550 -> 0.7503, Validierung 2025 0.7819 -> 0.7771).
ELO_STREUUNG_AKTIV_TAGE = 365      # "aktiv" = letzter Gang höchstens so lange her
ELO_STREUUNG_MIN_AKTIVE = 30       # darunter ist die Streuung nicht belastbar
ELO_STREUUNG_ERSATZ = 100.0        # dann gilt die frühere Skala (Version 1)
ELO_STREUUNG_UNTERGRENZE = 10.0    # schützt die ersten Feste vor Division ~0

# Einschwingphase: die ersten N Tage der Datenbasis liefern Historie für Elo,
# Form und Neigung, gehen aber NICHT ins Training. Dort sind die Ratings noch
# nicht eingeschwungen (Streuung 41 statt 77+), und die Gestellt-Quote lag
# deutlich höher (2023: 28.4 %, danach konstant ~21.5 %, in jedem Festtyp).
EINSCHWINGPHASE_TAGE = 365

# Ergebnis-Klassen (ML-1). Reihenfolge ist die Klassen-Indexierung.
KLASSEN = ["sieg_a", "gestellt", "sieg_b"]

# Fest-Typen (§4.2).
FEST_TYPEN = ["eidgenoessisch", "berg", "kantonal", "teilverband", "regional"]

# Elo-Gewichtung nach Fest-Wichtigkeit: ein Resultat an einem prestigeträchtigen
# Fest (grösseres, stärkeres Feld) bewegt das Rating stärker. Skaliert den
# K-Faktor je Gang. Startwerte -- empirisch gegen den Holdout validierbar.
FEST_K_GEWICHT = {
    "eidgenoessisch": 1.0,
    "berg": 0.8,
    "teilverband": 0.6,
    "kantonal": 0.6,
    "regional": 0.4,
}

# Höfliches Scraping (NFR-4).
SCRAPE_DELAY_SEKUNDEN = 2.0
USER_AGENT = "Schwingen-ML/1.0 (nicht-kommerziell; Hobby-Projekt)"

def ensure_dirs() -> None:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    WEB_PUBLIC_DIR.mkdir(parents=True, exist_ok=True)
    WEB_SERVER_DATA_DIR.mkdir(parents=True, exist_ok=True)
