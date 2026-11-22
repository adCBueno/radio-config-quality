# Radio Config Quality

Quality engineering for a small simulated **5G NR radio unit**: the software
that decides whether a carrier configuration (band, frequency, bandwidth,
subcarrier spacing, power) is valid before the radio transmits.

I built it to learn how radio software works and to try quality practices
that span the whole lifecycle, from requirements to tests to delivery,
including where AI fits in.

```
requirements/radio-unit.yaml ──> tests tagged with requirement ids ──> traceability report
          │                        (examples, boundaries, properties)      verified / failing / untested
          │                                                                     │
          └──────── untested requirement ──> LLM proposes test cases ──> draft for human review
```

## The radio unit

`rusim/` validates carrier configurations with rules from 3GPP:

| Rule | Source |
| --- | --- |
| NR-ARFCN ↔ frequency on the global raster (5 / 15 / 60 kHz steps) | TS 38.104, 5.4.2.1 |
| The carrier must fit inside its band's downlink range (n1, n3, n7, n28, n41, n77, n78) | TS 38.104, Table 5.2-1 |
| For FDD bands, the uplink carrier (downlink minus duplex spacing) must fit the uplink range | TS 38.104, Table 5.2-1 |
| The channel bandwidth must exist for the subcarrier spacing; report its resource blocks (N_RB) | TS 38.101-1, Table 5.3.2-1 |
| Power limits, no overlapping carriers, at most 4 carriers, atomic apply | product rules of this fictional radio |

A configuration is applied **all or nothing**: if any carrier breaks a rule,
nothing changes, and the error lists every broken rule with its requirement id.

```python
>>> RadioUnit().apply([CarrierConfig("c1", "n78", 636672, bandwidth_mhz=100, scs_khz=30, power_dbm=40)])
{'c1': ActiveCarrier(..., dl_center_khz=3550080, n_rb=273)}

>>> RadioUnit().apply([CarrierConfig("c1", "n78", 652000, 100, 30, 40)])
ConfigRejected: [REQ-RU-003] c1: carrier 3730000..3830000 kHz does not fit in n78 downlink 3300000..3800000 kHz
```

## Quality practices

**Requirements with ids.** Every rule is a requirement in
`requirements/radio-unit.yaml`, with its source (3GPP or product).

**Traceable tests.** Each test says which requirement it verifies:

```python
@pytest.mark.req("REQ-RU-007")
@pytest.mark.parametrize("power", [-0.1, 46.1, 60])
def test_power_out_of_range(power): ...
```

**Three kinds of tests.**
- *Known values* from the spec, e.g. NR-ARFCN 632628 = 3489.42 MHz.
- *Boundaries*: a carrier exactly at the band edge, power at exactly 0 and 46 dBm.
- *Property-based tests* with Hypothesis, which generate hundreds of inputs:
  every valid NR-ARFCN converts to a frequency and back to itself, and any
  carrier that fits in a TDD band with a valid bandwidth is accepted with the
  right N_RB.

**Traceability report.** `python -m quality.traceability` shows, per
requirement, how many tests verify it and whether they pass:

| Requirement | Title | Tests | Status |
| --- | --- | ---: | --- |
| REQ-RU-001 | Convert between NR-ARFCN and frequency on the global raster | 8 | ✅ verified |
| REQ-RU-003 | A carrier must fit entirely inside its downlink range | 4 | ✅ verified |
| REQ-RU-010 | A rejected configuration leaves the previous one unchanged | 1 | ✅ verified |
| REQ-RU-011 | At most 4 carriers, each with a unique id | 0 | ⚠️ untested |
| ... | | | |

Code coverage says which lines ran; this says which **requirements** are
actually checked. REQ-RU-011 is implemented but left untested on purpose, to
show the gap in the report and the next step.

**AI-assisted test design.** `python -m quality.propose_tests` sends each
untested requirement, the public API and an example test to an LLM and
writes the proposed tests to `proposals/` as a **draft for review**. They are
never added to the suite automatically: a generated test can encode the
wrong expected behaviour, so a person decides what correct means. Without an
API key it does a dry run and prints the prompt.

**CI.** GitHub Actions runs lint, the tests with a 90% coverage gate (now
94%), and puts the traceability report in the workflow summary. If an
`ANTHROPIC_API_KEY` secret is set, it also attaches the test proposals.

## Run it

```bash
pip install -e ".[dev]"
pytest --cov                       # 41 tests incl. property-based, coverage report
python -m quality.traceability     # requirement coverage (--strict fails on untested)
python -m quality.propose_tests    # dry run; set ANTHROPIC_API_KEY to call the model
```

## What I learned about NR along the way

- **NR-ARFCN** is just a number for a frequency on a global grid. The grid
  step depends on the range (5 kHz below 3 GHz, 15 kHz up to 24.25 GHz, 60 kHz
  above), so not every frequency can be a carrier center.
- **TDD vs FDD**: TDD bands (n41, n77, n78) use the same frequencies for
  uplink and downlink at different times; FDD bands (n1, n3, n7, n28) use two
  ranges separated by a fixed duplex spacing.
- **Subcarrier spacing and bandwidth** decide how many resource blocks fit in
  a channel: 100 MHz needs 30 kHz spacing and gives 273 resource blocks.

## Limitations

This is a learning model, not a real radio: it covers a few bands, uses the
global raster only (not each band's channel raster or SSB positions), and
ignores guard band details and later 3GPP release changes to the tables.

## Author

Adriana Calvo Bueno · [LinkedIn](https://www.linkedin.com/in/adriana-calvo-bueno/) · [GitHub](https://github.com/adCBueno)
