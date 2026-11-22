# Requirements traceability

**10 verified, 0 failing, 1 untested** out of 11 requirements.

| Requirement | Title | Source | Tests | Status |
| --- | --- | --- | ---: | --- |
| REQ-RU-001 | Convert between NR-ARFCN and frequency on the global raster | 3GPP TS 38.104 5.4.2.1 | 8 | ✅ verified |
| REQ-RU-002 | Reject an NR-ARFCN outside 0..3279165 | 3GPP TS 38.104 5.4.2.1 | 3 | ✅ verified |
| REQ-RU-003 | A carrier must use a supported band and fit entirely inside its downlink range | 3GPP TS 38.104 Table 5.2-1 | 4 | ✅ verified |
| REQ-RU-004 | Only 15 kHz and 30 kHz subcarrier spacing are supported | product | 1 | ✅ verified |
| REQ-RU-005 | The channel bandwidth must be valid for the subcarrier spacing | 3GPP TS 38.101-1 Table 5.3.2-1 | 8 | ✅ verified |
| REQ-RU-006 | Report the number of resource blocks (N_RB) of each active carrier | 3GPP TS 38.101-1 Table 5.3.2-1 | 7 | ✅ verified |
| REQ-RU-007 | Carrier power must be between 0 and 46 dBm | product | 5 | ✅ verified |
| REQ-RU-008 | For FDD bands, the uplink carrier must fit inside the uplink range | 3GPP TS 38.104 Table 5.2-1 | 2 | ✅ verified |
| REQ-RU-009 | Carriers on the same radio unit must not overlap in downlink | product | 2 | ✅ verified |
| REQ-RU-010 | A rejected configuration must leave the previous configuration unchanged | product | 1 | ✅ verified |
| REQ-RU-011 | At most 4 carriers, each with a unique id | product | 0 | ⚠️ untested |
