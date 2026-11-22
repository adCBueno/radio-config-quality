import pytest
from hypothesis import given
from hypothesis import strategies as st

from rusim.nr import BANDS, N_RB, ArfcnError, arfcn_to_khz, khz_to_arfcn, n_rb


@pytest.mark.req("REQ-RU-001")
@pytest.mark.parametrize("arfcn, khz", [
    (0, 0),
    (428000, 2_140_000),  # n1 downlink
    (600000, 3_000_000),  # first 15 kHz raster point
    (632628, 3_489_420),  # a common n78 carrier
    (2016667, 24_250_080),  # first FR2 raster point
])
def test_known_arfcn_values(arfcn, khz):
    assert arfcn_to_khz(arfcn) == khz
    assert khz_to_arfcn(khz) == arfcn


@pytest.mark.req("REQ-RU-001")
@given(st.integers(min_value=0, max_value=3_279_165))
def test_arfcn_round_trip(arfcn):
    """Property: every valid NR-ARFCN maps to a frequency that maps back to it."""
    assert khz_to_arfcn(arfcn_to_khz(arfcn)) == arfcn


@pytest.mark.req("REQ-RU-001")
@given(st.integers(min_value=0, max_value=3_279_164))
def test_frequency_grows_with_arfcn(arfcn):
    assert arfcn_to_khz(arfcn + 1) > arfcn_to_khz(arfcn)


@pytest.mark.req("REQ-RU-001")
def test_frequency_off_the_raster_is_rejected():
    with pytest.raises(ArfcnError, match="raster"):
        khz_to_arfcn(3_000_010)  # 15 kHz raster above 3 GHz


@pytest.mark.req("REQ-RU-002")
@pytest.mark.parametrize("arfcn", [-1, 3_279_166, 10**9])
def test_arfcn_out_of_range(arfcn):
    with pytest.raises(ArfcnError):
        arfcn_to_khz(arfcn)


@pytest.mark.req("REQ-RU-005", "REQ-RU-006")
@pytest.mark.parametrize("scs, bw, expected", [(15, 5, 25), (15, 20, 106), (15, 50, 270), (30, 100, 273), (30, 40, 106)])
def test_n_rb_table(scs, bw, expected):
    assert n_rb(scs, bw) == expected


@pytest.mark.req("REQ-RU-005")
def test_100_mhz_needs_30_khz_scs():
    assert n_rb(15, 100) is None


def test_tables_are_consistent():
    # wider channel -> more resource blocks; FDD bands have a positive duplex spacing
    for table in N_RB.values():
        values = [table[bw] for bw in sorted(table)]
        assert values == sorted(values)
    assert all(b.duplex_spacing_khz > 0 for b in BANDS.values() if b.duplex == "FDD")
