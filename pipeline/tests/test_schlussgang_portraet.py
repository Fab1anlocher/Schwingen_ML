"""Tests für die Plausibilitätsprüfung von Körpermassen aus Schlussgang-Porträts.

Hintergrund: ein reales Profil (Peter Roth) hatte auf schlussgang.ch selbst
Grösse=97cm / Gewicht=177kg vertauscht -- kein Scraper-Bug auf unserer Seite,
sondern ein Dateneingabefehler an der Quelle. Da 97cm für einen erwachsenen
Schwinger physisch unmöglich ist, aber innerhalb der bisherigen Logik
klaglos als echter Messwert ins Clustering/die Analyse-Streudiagramme
eingeflossen wäre, werden unplausible Werte jetzt schon beim Parsen verworfen.
"""
from __future__ import annotations

from pipeline.scrape.schlussgang_portraet import _koerpermass


def test_plausibler_wert_bleibt_erhalten():
    assert _koerpermass("183", 140, 230) == 183.0
    assert _koerpermass("103,5", 40, 250) == 103.5  # Komma als Dezimaltrennzeichen


def test_unplausibler_wert_wird_verworfen():
    # Realer Fall: Peter Roth, field_portrait_body_size="97" (Grösse in cm).
    assert _koerpermass("97", 140, 230) is None


def test_grenzwerte_sind_inklusiv():
    assert _koerpermass("140", 140, 230) == 140.0
    assert _koerpermass("230", 140, 230) == 230.0
    assert _koerpermass("139.9", 140, 230) is None
    assert _koerpermass("230.1", 140, 230) is None


def test_kaputter_wert_gibt_none():
    assert _koerpermass(None, 140, 230) is None
    assert _koerpermass("", 140, 230) is None
    assert _koerpermass("k.A.", 140, 230) is None
