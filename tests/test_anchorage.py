"""Anchorage / lap splice per TCVN 5574:2018 10.3.5-10.3.6 vs Excel '05. TINH CHIEU DAI NEO THEP'."""

from tcvn5574 import calculate_anchorage_length, calculate_lap_splice_length, get_concrete, get_rebar

B30, CB400 = get_concrete("B30"), get_rebar("CB400-V")


def test_anchorage_excel():
    t = calculate_anchorage_length(30, B30, CB400)
    assert abs(t.Rbond_MPa - 2.875) < 1e-3 and abs(t.l0_an_mm - 913.0) < 0.5 and t.alpha1 == 1.0
    c = calculate_anchorage_length(30, B30, CB400, is_tension=False)
    assert c.alpha1 == 0.75 and abs(c.lan_mm - 684.8) < 0.5


def test_anchorage_minimums_and_eta2():
    small = calculate_anchorage_length(10, B30, CB400, ratio_As=0.2)
    assert small.lan_mm == round(max(0.3 * 304.3, 150, 200), 1)
    assert calculate_anchorage_length(36, B30, CB400).eta2 == 0.9


def test_lap_splice():
    assert abs(calculate_lap_splice_length(30, B30, CB400, spliced_percentage=50).llap_mm - 1095.7) < 1
    assert abs(calculate_lap_splice_length(30, B30, CB400, spliced_percentage=100).llap_mm - 1826.1) < 1
    assert calculate_lap_splice_length(30, B30, CB400, spliced_percentage=75).alpha2 == 1.6
    assert calculate_lap_splice_length(30, B30, CB400, is_tension=False, spliced_percentage=100).alpha2 == 1.2
    # plain bars: base value only up to 25 %
    assert calculate_lap_splice_length(12, B30, get_rebar("CB240-T"), spliced_percentage=50).alpha2 > 1.2
