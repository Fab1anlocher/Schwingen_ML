"""Kantonalverband -> politischer Kanton (für die Schweiz-Karte in der Web-App).

`Schwinger.kanton` ist trotz des Feldnamens der **Kantonal-/Gauverband**
(schlussgang.ch: field_portrait_cant_association) — bei grossen Verbänden wie
Bern in Regionalverbände aufgeteilt (Oberland, Emmental, Mittelland,
Oberaargau, Seeland, Berner-Jura), die nicht 1:1 auf die 26 politischen
Kantone abbilden. Für eine Kantons-Karte werden diese hier zusammengeführt;
Verbände, die mehrere Kantone abdecken (z.B. "Ob- und Nidwalden"), tragen zu
allen betroffenen Kantonen bei (bewusste Vereinfachung, keine Aufteilung nach
Kopfzahl möglich).

Kanton-Namen exakt wie in web/lib/schweiz-kantone.ts (aus dem GeoJSON).
"""
from __future__ import annotations

KANTONALVERBAND_ZU_KANTON: dict[str, list[str]] = {
    "Luzern": ["Luzern"],
    "Oberland": ["Bern"],
    "Fribourgeoise": ["Fribourg"],
    "Schwyz": ["Schwyz"],
    "Aargau": ["Aargau"],
    "St. Gallen": ["St. Gallen"],
    "Emmental": ["Bern"],
    "Ob- und Nidwalden": ["Obwalden", "Nidwalden"],
    "Mittelland": ["Bern"],
    "Zug": ["Zug"],
    "Zürich": ["Zürich"],
    "Thurgau": ["Thurgau"],
    "Solothurn": ["Solothurn"],
    "Appenzell": ["Appenzell Ausserrhoden", "Appenzell Innerrhoden"],
    "Oberaargau": ["Bern"],
    "Uri": ["Uri"],
    "Seeland": ["Bern"],
    "Baselland": ["Basel-Landschaft"],
    "Graubünden": ["Graubünden"],
    "Vaudoise": ["Vaud"],
    "Valaisanne": ["Valais"],
    "Schaffhausen": ["Schaffhausen"],
    "Glarus": ["Glarus"],
    "Genevoise": ["Genève"],
    "Berner-Jura": ["Bern"],
    "Neuchâteloise": ["Neuchâtel"],
    "Jura": ["Jura"],
    "Basel-Stadt": ["Basel-Stadt"],
}


def kantone_fuer(kantonalverband: str | None) -> list[str]:
    if not kantonalverband:
        return []
    return KANTONALVERBAND_ZU_KANTON.get(kantonalverband, [])
