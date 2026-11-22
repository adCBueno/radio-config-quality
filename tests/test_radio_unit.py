import pytest
from hypothesis import given
from hypothesis import strategies as st

from rusim import CarrierConfig, ConfigRejected, RadioUnit
from rusim.nr import BANDS, N_RB, khz_to_arfcn


def carrier(carrier_id="c1", band="n78", center_khz=3_550_080, bw=100, scs=30, power=40.0):
    return CarrierConfig(carrier_id, band, khz_to_arfcn(center_khz), bw, scs, power)


def rejected_requirements(configs):
    with pytest.raises(ConfigRejected) as err:
        RadioUnit().apply(configs)
    return {v.requirement for v in err.value.violations}


@pytest.mark.req("REQ-RU-006")
def test_valid_tdd_carrier_is_applied_with_its_n_rb():
    active = RadioUnit().apply([carrier()])["c1"]
    assert active.n_rb == 273
    assert active.dl_center_khz == active.ul_center_khz  # TDD


@pytest.mark.req("REQ-RU-003")
def test_unknown_band():
    assert "REQ-RU-003" in rejected_requirements([carrier(band="n999")])


@pytest.mark.req("REQ-RU-003")
def test_carrier_must_fit_inside_band():
    # 100 MHz centred at 3780 MHz would reach 3830 MHz, above n78's 3800 MHz edge
    assert rejected_requirements([carrier(center_khz=3_780_000)]) == {"REQ-RU-003"}


@pytest.mark.req("REQ-RU-003")
def test_carrier_exactly_at_band_edge_is_accepted():
    RadioUnit().apply([carrier(center_khz=3_750_000)])  # 3700..3800 MHz


@pytest.mark.req("REQ-RU-004")
def test_unsupported_scs():
    assert "REQ-RU-004" in rejected_requirements([carrier(scs=60)])


@pytest.mark.req("REQ-RU-005")
def test_invalid_bandwidth_for_scs():
    assert "REQ-RU-005" in rejected_requirements([carrier(bw=100, scs=15)])


@pytest.mark.req("REQ-RU-007")
@pytest.mark.parametrize("power", [-0.1, 46.1, 60])
def test_power_out_of_range(power):
    assert rejected_requirements([carrier(power=power)]) == {"REQ-RU-007"}


@pytest.mark.req("REQ-RU-007")
@pytest.mark.parametrize("power", [0.0, 46.0])
def test_power_limits_are_inclusive(power):
    RadioUnit().apply([carrier(power=power)])


@pytest.mark.req("REQ-RU-008")
def test_fdd_uplink_is_derived_from_duplex_spacing():
    active = RadioUnit().apply([carrier(band="n1", center_khz=2_140_000, bw=20, scs=15)])["c1"]
    assert active.ul_center_khz == 2_140_000 - 190_000


@pytest.mark.req("REQ-RU-008")
def test_fdd_uplink_must_fit():
    # n28 downlink 758-803 MHz, uplink 703-748 MHz (55 MHz spacing).
    # Make the band's uplink narrower than its downlink to force an uplink-only violation.
    from dataclasses import replace

    from rusim import nr
    narrow = replace(BANDS["n28"], ul_high_khz=740_000)
    original = nr.BANDS["n28"]
    nr.BANDS["n28"] = narrow
    try:
        assert rejected_requirements([carrier(band="n28", center_khz=793_000, bw=20, scs=15)]) == {"REQ-RU-008"}
    finally:
        nr.BANDS["n28"] = original


@pytest.mark.req("REQ-RU-009")
def test_overlapping_carriers_are_rejected():
    a = carrier("a", center_khz=3_399_990, bw=100)  # 3349.99..3449.99 MHz
    b = carrier("b", center_khz=3_480_000, bw=100)  # 3430..3530 MHz, overlaps a
    assert rejected_requirements([a, b]) == {"REQ-RU-009"}


@pytest.mark.req("REQ-RU-009")
def test_adjacent_carriers_are_accepted():
    a = carrier("a", center_khz=3_399_990, bw=100)  # ends at 3449.990 MHz
    b = carrier("b", center_khz=3_499_995, bw=100)  # starts at 3449.995 MHz
    RadioUnit().apply([a, b])


@pytest.mark.req("REQ-RU-010")
def test_rejected_config_keeps_previous_state():
    ru = RadioUnit()
    good = ru.apply([carrier("c1")])
    with pytest.raises(ConfigRejected):
        ru.apply([carrier("c1"), carrier("c2", power=99)])
    assert ru.carriers == good


@pytest.mark.req("REQ-RU-003", "REQ-RU-005", "REQ-RU-006")
@given(
    band=st.sampled_from(["n41", "n77", "n78"]),
    scs=st.sampled_from(sorted(N_RB)),
    data=st.data(),
)
def test_any_carrier_inside_a_tdd_band_is_accepted(band, scs, data):
    """Property: if the carrier fits and the bandwidth is valid, it is accepted with the right N_RB."""
    bw = data.draw(st.sampled_from(sorted(N_RB[scs])))
    b = BANDS[band]
    half = bw * 500
    center = data.draw(st.integers(min_value=(b.dl_low_khz + half) // 15 + 1, max_value=(b.dl_high_khz - half) // 15))
    center_khz = center * 15  # stay on the 15 kHz global raster
    if center_khz < 3_000_000:
        center_khz = (center_khz // 5) * 5
    active = RadioUnit().apply([carrier(band=band, center_khz=center_khz, bw=bw, scs=scs)])["c1"]
    assert active.n_rb == N_RB[scs][bw]
