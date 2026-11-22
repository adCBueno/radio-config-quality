"""A simplified radio unit that accepts carrier configurations.

Every rule is linked to a requirement id in requirements/radio-unit.yaml, so
a rejected configuration says which requirement it would break.
"""

from __future__ import annotations

from dataclasses import dataclass

from .nr import BANDS, ArfcnError, Duplex, arfcn_to_khz, n_rb

MAX_POWER_DBM = 46.0  # product limit of this (fictional) radio unit
MAX_CARRIERS = 4


@dataclass(frozen=True)
class CarrierConfig:
    carrier_id: str
    band: str
    dl_arfcn: int  # center of the carrier
    bandwidth_mhz: int
    scs_khz: int
    power_dbm: float


@dataclass(frozen=True)
class Violation:
    requirement: str
    carrier_id: str
    message: str


@dataclass(frozen=True)
class ActiveCarrier:
    config: CarrierConfig
    dl_center_khz: int
    ul_center_khz: int
    n_rb: int


class ConfigRejected(Exception):
    def __init__(self, violations: list[Violation]):
        self.violations = violations
        super().__init__("; ".join(f"[{v.requirement}] {v.carrier_id}: {v.message}" for v in violations))


def validate_carrier(cfg: CarrierConfig) -> list[Violation]:
    issues: list[Violation] = []

    def fail(req: str, msg: str) -> None:
        issues.append(Violation(req, cfg.carrier_id, msg))

    band = BANDS.get(cfg.band)
    if band is None:
        fail("REQ-RU-003", f"band {cfg.band} is not supported")
    if cfg.scs_khz not in (15, 30):
        fail("REQ-RU-004", f"subcarrier spacing {cfg.scs_khz} kHz is not supported (15 or 30)")
    elif n_rb(cfg.scs_khz, cfg.bandwidth_mhz) is None:
        fail("REQ-RU-005", f"{cfg.bandwidth_mhz} MHz is not a valid channel bandwidth for {cfg.scs_khz} kHz SCS")
    if not 0.0 <= cfg.power_dbm <= MAX_POWER_DBM:
        fail("REQ-RU-007", f"power {cfg.power_dbm} dBm is outside 0..{MAX_POWER_DBM} dBm")

    try:
        center = arfcn_to_khz(cfg.dl_arfcn)
    except ArfcnError as err:
        fail("REQ-RU-002", str(err))
        return issues

    if band is not None:
        half = cfg.bandwidth_mhz * 500
        if center - half < band.dl_low_khz or center + half > band.dl_high_khz:
            fail("REQ-RU-003", f"carrier {center - half}..{center + half} kHz does not fit in {band.name} downlink "
                               f"{band.dl_low_khz}..{band.dl_high_khz} kHz")
        if band.duplex is Duplex.FDD:
            ul = center - band.duplex_spacing_khz
            if ul - half < band.ul_low_khz or ul + half > band.ul_high_khz:
                fail("REQ-RU-008", f"uplink carrier around {ul} kHz does not fit in {band.name} uplink")
    return issues


def _overlaps(carriers: list[CarrierConfig]) -> list[Violation]:
    issues = []
    spans = []
    for cfg in carriers:
        try:
            center = arfcn_to_khz(cfg.dl_arfcn)
        except ArfcnError:
            continue
        spans.append((center - cfg.bandwidth_mhz * 500, center + cfg.bandwidth_mhz * 500, cfg.carrier_id))
    spans.sort()
    for (_, end_a, id_a), (start_b, _, id_b) in zip(spans, spans[1:], strict=False):
        if start_b < end_a:
            issues.append(Violation("REQ-RU-009", id_b, f"overlaps carrier {id_a} in downlink"))
    return issues


class RadioUnit:
    def __init__(self) -> None:
        self._carriers: dict[str, ActiveCarrier] = {}

    @property
    def carriers(self) -> dict[str, ActiveCarrier]:
        return dict(self._carriers)

    def apply(self, configs: list[CarrierConfig]) -> dict[str, ActiveCarrier]:
        """Replace the whole configuration. All carriers are validated first:
        if anything is wrong, nothing is applied (REQ-RU-010)."""
        violations: list[Violation] = []
        if len(configs) > MAX_CARRIERS:
            violations.append(Violation("REQ-RU-011", "*", f"{len(configs)} carriers, at most {MAX_CARRIERS}"))
        ids = [c.carrier_id for c in configs]
        for dup in sorted({i for i in ids if ids.count(i) > 1}):
            violations.append(Violation("REQ-RU-011", dup, "carrier id used more than once"))
        for cfg in configs:
            violations += validate_carrier(cfg)
        violations += _overlaps(configs)
        if violations:
            raise ConfigRejected(violations)

        new_state = {}
        for cfg in configs:
            dl = arfcn_to_khz(cfg.dl_arfcn)
            band = BANDS[cfg.band]
            new_state[cfg.carrier_id] = ActiveCarrier(
                cfg, dl, dl - band.duplex_spacing_khz, n_rb(cfg.scs_khz, cfg.bandwidth_mhz) or 0
            )
        self._carriers = new_state
        return self.carriers
