"""Tests für das Kopf-an-Kopf-Merkmal (geglättete direkte Duell-Bilanz)."""
from __future__ import annotations

from pipeline.features import _kopf_an_kopf_vorteil


def test_ohne_historie_neutral():
    assert _kopf_an_kopf_vorteil("a", "b", {}) == 0.0


def test_klare_serie_ergibt_starken_ausschlag():
    # "moser" < "schlegel" -> moser ist kanonisch kleiner; 4/4 Niederlagen (0.0).
    hist = {("moser", "schlegel"): [0.0, 0.0, 0.0, 0.0]}
    v_moser = _kopf_an_kopf_vorteil("moser", "schlegel", hist)
    v_schlegel = _kopf_an_kopf_vorteil("schlegel", "moser", hist)
    assert v_moser < -0.5  # deutlicher Nachteil
    assert v_schlegel > 0.5  # deutlicher Vorteil
    assert v_moser == -v_schlegel  # symmetrisch


def test_einzelnes_duell_wird_gegen_neutral_gedaempft():
    # Ein einziger Sieg soll NICHT sofort auf +1 ausschlagen (kleine Stichprobe).
    hist = {("a", "b"): [1.0]}
    v = _kopf_an_kopf_vorteil("a", "b", hist)
    assert 0.0 < v < 0.5


def test_ausgeglichene_bilanz_nahe_null():
    hist = {("a", "b"): [1.0, 0.0, 1.0, 0.0]}
    assert abs(_kopf_an_kopf_vorteil("a", "b", hist)) < 1e-9


def test_gestellt_serie_neutral():
    hist = {("a", "b"): [0.5, 0.5, 0.5]}
    assert abs(_kopf_an_kopf_vorteil("a", "b", hist)) < 1e-9
