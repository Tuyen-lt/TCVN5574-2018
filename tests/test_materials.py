"""Materials vs TCVN 5574:2018 Bảng 6, 7, 10, 13, 14 and 6.2.3.3."""

import pytest
from tcvn5574 import HumidityCondition, RebarType, bar_area, get_concrete, get_rebar


@pytest.mark.parametrize(
    "grade, Rb, Rbt, Rb_ser, Rbt_ser, Eb",
    [
        ("B15", 8.5, 0.75, 11.0, 1.10, 24000),
        ("B20", 11.5, 0.90, 15.0, 1.35, 27500),
        ("B25", 14.5, 1.05, 18.5, 1.55, 30000),
        ("B30", 17.0, 1.15, 22.0, 1.75, 32500),
        ("B45", 25.0, 1.50, 32.0, 2.25, 37000),
        ("B60", 33.0, 1.80, 43.0, 2.75, 39500),
    ],
)
def test_concrete_tables(grade, Rb, Rbt, Rb_ser, Rbt_ser, Eb):
    c = get_concrete(grade)
    assert (c.Rb, c.Rbt, c.Rb_ser, c.Rbt_ser, c.Eb) == (Rb, Rbt, Rb_ser, Rbt_ser, Eb)


def test_creep():
    c = get_concrete("B30")
    assert c.get_creep_coefficient(HumidityCondition.MEDIUM) == 2.3
    assert c.get_creep_coefficient(HumidityCondition.HIGH) == 1.6
    assert get_concrete("B7.5").get_creep_coefficient("<40%") == 5.6  # below B10 -> B10 values


@pytest.mark.parametrize(
    "grade, Rs, Rsc, Rsw",
    [("CB240-T", 210, 210, 170), ("CB300-V", 260, 260, 210), ("CB400-V", 350, 350, 280), ("CB500-V", 435, 435, 300)],
)
def test_rebar_tables(grade, Rs, Rsc, Rsw):
    r = get_rebar(grade)
    assert (r.Rs, r.Rsc, r.Rsw, r.Es) == (Rs, Rsc, Rsw, 200000.0)


def test_rebar_type_and_geometry():
    assert get_rebar("CB240-T").rebar_type == RebarType.PLAIN
    assert get_rebar("CB400").rebar_type == RebarType.DEFORMED
    assert abs(bar_area(20) - 314.159) < 0.01


def test_material_factor_and_override_validation():
    with pytest.raises(ValueError, match="gamma_b"):
        get_concrete("B25", gamma_b=0)
    with pytest.raises(ValueError, match="rbt_override"):
        get_concrete("B25", rbt_override=-1)
    with pytest.raises(ValueError, match="gamma_s"):
        get_rebar("CB400-V", gamma_s=0)
    with pytest.raises(ValueError, match="rsw_override"):
        get_rebar("CB400-V", rsw_override=0)


def test_b35_wall_benchmark_material_pair_and_b35_table():
    concrete = get_concrete("B35")
    assert concrete.Rb == 19.5
    assert concrete.Eb == 34500
    assert get_concrete("B3.5").Eb == 9500
