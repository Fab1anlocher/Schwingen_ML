"""Kantonalverband -> politischer Kanton (für die Schweiz-Karte in der Web-App).

`Schwinger.kanton` ist trotz des Feldnamens der **Kantonal-/Gauverband**
(schlussgang.ch: field_portrait_cant_association), nicht der politische
Kanton. Die 5 Teilverbände gliedern sich in insgesamt 29 Kantonal-/
Gauverbände; grosse Kantone wie Bern sind darin in mehrere Regionalverbände
aufgeteilt (Oberland, Emmental, Mittelland, Oberaargau, Seeland, Berner-Jura),
die nicht 1:1 auf die 26 politischen Kantone abbilden. Für die Kartendarstellung
werden diese hier zusammengeführt; Verbände, die mehrere Kantone abdecken
(z.B. "Ob- und Nidwalden", "Appenzell"), tragen zu allen betroffenen Kantonen
bei (bewusste Vereinfachung, keine Aufteilung nach Kopfzahl möglich).

Struktur/Namen nach der offiziellen ESV-Gliederung der 5 Teilverbände in
29 Kantonal-/Gauverbände. Kanton-Namen exakt wie in web/lib/schweiz-kantone.ts
(aus dem GeoJSON) — daher z.B. "Fribourgeoise" -> "Fribourg", nicht "Freiburg".
"""
from __future__ import annotations

KANTONALVERBAND_ZU_KANTON: dict[str, list[str]] = {
    # Berner Kantonal-Schwingerverband
    "Berner-Jura": ["Bern"],
    "Emmental": ["Bern"],
    "Mittelland": ["Bern"],
    "Oberaargau": ["Bern"],
    "Oberland": ["Bern"],
    "Seeland": ["Bern"],
    # Innerschweizer Schwingerverband
    "Luzern": ["Luzern"],
    "Ob- und Nidwalden": ["Obwalden", "Nidwalden"],
    "Schwyz": ["Schwyz"],
    "Tessin": ["Ticino"],  # seit 2013-2018 im Innerschweizer Verband; aktuell keine erfassten Schwinger
    "Uri": ["Uri"],
    "Zug": ["Zug"],
    # Nordostschweizer Schwingerverband
    "Appenzell": ["Appenzell Ausserrhoden", "Appenzell Innerrhoden"],
    "Glarus": ["Glarus"],
    "Graubünden": ["Graubünden"],
    "Schaffhausen": ["Schaffhausen"],
    "St. Gallen": ["St. Gallen"],
    "Thurgau": ["Thurgau"],
    "Zürich": ["Zürich"],
    # Nordwestschweizer Schwingerverband
    "Aargau": ["Aargau"],
    "Baselland": ["Basel-Landschaft"],
    "Basel-Stadt": ["Basel-Stadt"],
    "Solothurn": ["Solothurn"],
    # Südwestschweizer Schwingerverband
    "Fribourgeoise": ["Fribourg"],
    "Genevoise": ["Genève"],
    "Jura": ["Jura"],
    "Neuchâteloise": ["Neuchâtel"],
    "Vaudoise": ["Vaud"],
    "Valaisanne": ["Valais"],
}

assert len(KANTONALVERBAND_ZU_KANTON) == 29, "Es sind 29 Kantonal-/Gauverbände (ESV-Gliederung)"


def kantone_fuer(kantonalverband: str | None) -> list[str]:
    if not kantonalverband:
        return []
    return KANTONALVERBAND_ZU_KANTON.get(kantonalverband, [])
