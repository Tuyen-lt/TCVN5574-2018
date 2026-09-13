"""Tests for batch beam processing."""

from tcvn5574.batch.beam_batch import process_beam_batch


def test_process_beam_batch():
    rows = [
        {"story": "LAU 1", "beam": "B1", "loc": 0.1, "load": "COMB1", "M3": -14.68, "V2": -32.46, "b": 300, "h": 600},
        {"story": "LAU 1", "beam": "B1", "loc": 5.0, "load": "COMB1", "M3": -30.19, "V2": 246.33, "b": 300, "h": 600},
    ]
    results = process_beam_batch(rows)
    assert len(results) == 2
    assert all(r.h0_mm == 560 and r.As_req_cm2 > 0 and r.stirrup_spacing_mm > 0 and r.is_shear_safe for r in results)
    assert results[1].stirrup_spacing_mm < results[0].stirrup_spacing_mm
