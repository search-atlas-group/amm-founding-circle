# Command-center context map (fictional example)

**Overall owner:** `<name>`  
**Refresh timestamp:** `<timestamp>`  
**Status:** `DRAFT`

| Context | Field | Source | Owner | Freshness | Unknown / exception rule |
|---|---|---|---|---|---|
| Fulfillment | active services | redacted CRM export | `<name>` | daily | missing scope = UNKNOWN |
| Fulfillment | delivery stage | service board | `<name>` | daily | no evidence = REVIEW |
| Revenue | next invoice | redacted billing export | `<name>` | daily | absent invoice ≠ paid |
| Revenue | collection status | redacted billing export | `<name>` | daily | stale payment = REVIEW |
| Meeting | last / next meeting | redacted calendar export | `<name>` | daily | identity mismatch = UNKNOWN |
| Meeting | disposition | approved transcript summary | `<name>` | after meeting | no transcript = UNKNOWN |

## First read-only slice

`<Describe the smallest useful view and attach its evidence.>`

## Review gate

No billing write, client message, permission change, transcript exposure, or live integration until a named owner reviews this map.
