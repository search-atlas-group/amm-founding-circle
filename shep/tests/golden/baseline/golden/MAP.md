# Staging golden to standalone destination map

These fixtures are staging evidence for exact ancestors, not the final package layout.

| Staging fixture | Standalone destination |
|---|---|
| `mbm/help.json`, `ae/help.json` | `tests/golden/cli/{mbm,ae}/help.json` |
| `mbm/dump.json`, `ae/dump.json` | `tests/golden/cli/{mbm,ae}/dump.json` |
| `mbm/snapshot.json`, `ae/snapshot-unavailable.json` | `tests/golden/cli/{mbm,ae}/snapshot.json` |
| `mbm/mission-create.json`, `mbm/mission-list.json`, AE unavailable fixtures | `tests/golden/cli/{mbm,ae}/missions/` |
| `mbm/control-*.json`, `ae/control-unavailable.json` | `tests/golden/control/{mbm,ae}/` |
| `mbm/sweep-draft-only.json`, `ae/sweep-unavailable.json` | `tests/golden/cli/{mbm,ae}/sweep.json` |
| `ae/gateway-*.json` | `tests/golden/gateway/ae/` |
| `*/invalid.json` | `tests/golden/cli/{mbm,ae}/invalid.json` |

Final tests consume copies through the executable normalizer and must also assert the source SHA recorded in each ancestor manifest.
