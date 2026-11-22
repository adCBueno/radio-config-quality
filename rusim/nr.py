"""5G NR basics a radio unit needs to validate a carrier configuration.

All frequencies are integers in kHz to avoid floating point rounding.

Sources (a small subset, for learning purposes):
- NR-ARFCN and the global frequency raster: 3GPP TS 38.104, section 5.4.2.1
- Operating bands: 3GPP TS 38.104 Table 5.2-1
- Maximum transmission bandwidth (N_RB): 3GPP TS 38.101-1 Table 5.3.2-1
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class Duplex(StrEnum):
    FDD = "FDD"  # separate uplink and downlink frequencies
    TDD = "TDD"  # uplink and downlink share the band, split in time


@dataclass(frozen=True)
class Band:
    name: str
    duplex: Duplex
    dl_low_khz: int
    dl_high_khz: int
    ul_low_khz: int
    ul_high_khz: int

    @property
    def duplex_spacing_khz(self) -> int:
        """Distance from downlink to uplink, 0 for TDD."""
        return self.dl_low_khz - self.ul_low_khz


def _mhz(value: float) -> int:
    return int(round(value * 1000))


def _fdd(name: str, ul: tuple[float, float], dl: tuple[float, float]) -> Band:
    return Band(name, Duplex.FDD, _mhz(dl[0]), _mhz(dl[1]), _mhz(ul[0]), _mhz(ul[1]))


def _tdd(name: str, low: float, high: float) -> Band:
    return Band(name, Duplex.TDD, _mhz(low), _mhz(high), _mhz(low), _mhz(high))


BANDS: dict[str, Band] = {b.name: b for b in [
    _fdd("n1", ul=(1920, 1980), dl=(2110, 2170)),
    _fdd("n3", ul=(1710, 1785), dl=(1805, 1880)),
    _fdd("n7", ul=(2500, 2570), dl=(2620, 2690)),
    _fdd("n28", ul=(703, 748), dl=(758, 803)),
    _tdd("n41", 2496, 2690),
    _tdd("n77", 3300, 4200),
    _tdd("n78", 3300, 3800),
]}

# TS 38.104 5.4.2.1: (N_REF range, delta F_Global, F_REF-Offs, N_REF-Offs)
_RASTER = [
    (range(0, 600_000), 5, 0, 0),
    (range(600_000, 2_016_667), 15, 3_000_000, 600_000),
    (range(2_016_667, 3_279_166), 60, 24_250_080, 2_016_667),
]

# TS 38.101-1 Table 5.3.2-1, FR1: {SCS kHz: {channel bandwidth MHz: N_RB}}
N_RB: dict[int, dict[int, int]] = {
    15: {5: 25, 10: 52, 15: 79, 20: 106, 25: 133, 30: 160, 40: 216, 50: 270},
    30: {5: 11, 10: 24, 15: 38, 20: 51, 25: 65, 30: 78, 40: 106, 50: 133,
         60: 162, 70: 189, 80: 217, 90: 245, 100: 273},
}

SUPPORTED_SCS_KHZ = frozenset(N_RB)


class ArfcnError(ValueError):
    pass


def arfcn_to_khz(arfcn: int) -> int:
    """NR-ARFCN -> reference frequency: F_REF = F_REF-Offs + dF_Global * (N_REF - N_REF-Offs)."""
    for numbers, step, f_offs, n_offs in _RASTER:
        if arfcn in numbers:
            return f_offs + step * (arfcn - n_offs)
    raise ArfcnError(f"NR-ARFCN {arfcn} is outside 0..3279165")


def khz_to_arfcn(freq_khz: int) -> int:
    """Reference frequency -> NR-ARFCN. The frequency must be on the global raster."""
    for numbers, step, f_offs, n_offs in _RASTER:
        low = f_offs + step * (numbers.start - n_offs)
        high = f_offs + step * (numbers.stop - 1 - n_offs)
        if low <= freq_khz <= high:
            if (freq_khz - f_offs) % step:
                raise ArfcnError(f"{freq_khz} kHz is not on the {step} kHz global raster")
            return n_offs + (freq_khz - f_offs) // step
    raise ArfcnError(f"{freq_khz} kHz is not covered by the NR global raster")


def n_rb(scs_khz: int, bandwidth_mhz: int) -> int | None:
    """Number of resource blocks for this SCS and channel bandwidth, or None if not allowed."""
    return N_RB.get(scs_khz, {}).get(bandwidth_mhz)
