# Command Center — three-context brief

**Origin:** mastermind session, segments 564–587  
**Status:** design brief; not a claim that any connector is installed  
**Owner model from session:** Fulfillment context — Jessica; Revenue context — Brandon; Meeting context — Jonathan. Verify names and roles against the actual team before implementation.

## Page 1 — Fulfillment context

### Purpose

Show which services are active for each client, where each service is in delivery, and whether the expected outcome is on track.

### Initial service buckets named in the session

- SEO implementation
- Web implementation
- PPC / paid media
- Meta ads
- Local / GBP work where applicable

### Initial data contract

| Field | Meaning | Candidate source |
|---|---|---|
| Client | active client identity | CRM / GHL |
| Active services | what the client is paying for | CRM tags / scope |
| Service owner | accountable fulfillment owner | team roster |
| Current stage | where delivery stands | service system |
| Latest evidence | report, dashboard, or artifact | service system |
| Outcome signal | current performance indicator | service dashboard / GA4 / SearchAtlas |
| Blocker | missing access, review, or work | lane board |

### Acceptance checks

- The view can enumerate active clients and their active service tags.
- Every active service has one owner and a current status.
- The view links to evidence rather than claiming performance from a blank status.
- Missing connectors are shown as `UNKNOWN`, not silently treated as healthy.

## Page 2 — Revenue context

### Purpose

Make billing state visible enough to catch missed billing, upcoming billing, and payment exceptions before they become operational surprises.

### Initial data contract

| Field | Meaning | Candidate source |
|---|---|---|
| Client | billed account | FreshBooks / CRM |
| Last invoice | most recent bill date and amount | FreshBooks |
| Next invoice | expected next bill date and amount | FreshBooks |
| Payment channel | ACH, card, or other | FreshBooks |
| Collection status | paid, pending, failed, unknown | FreshBooks |
| Revenue owner | accountable context owner | team roster |
| Exception | service delivered without expected billing, or other mismatch | command center rules |

### Acceptance checks

- Last and next billing data can be traced to the billing source.
- Payment status is current as-of a stated timestamp.
- An exception is surfaced when service status and billing status disagree.
- The system does not charge, refund, or alter billing as part of this read-only view.

## Page 3 — Meeting context

### Purpose

Know when the client was last met, when the next meeting is due, what was decided, whether the meeting happened, and what the client sentiment signal is.

### Initial data contract

| Field | Meaning | Candidate source |
|---|---|---|
| Client | account identity | CRM / meeting roster |
| Last meeting | occurrence and date | Zoom |
| Next meeting | scheduled occurrence | Zoom / calendar |
| Transcript | private meeting artifact | Zoom transcript API |
| Disposition | outcome and next action | transcript grading skill |
| Sentiment | directional signal, not a diagnosis | transcript / email analysis |
| Missed meeting | expected meeting without evidence | schedule vs. occurrence |
| Meeting owner | accountable context owner | team roster |

### Implementation sequence

1. Confirm Zoom API scopes and a real read-only meeting fetch.
2. Add the completion webhook plus a bounded polling fallback.
3. Store private transcripts and meeting metadata in a SQLite-backed repository.
4. Run the transcript-grading skill on a test set and inspect outputs.
5. Add the next-meeting and missed-meeting checks.
6. Add sentiment only after disposition and identity matching are reliable.

## Cross-context rules

- This is a read-first command center; no billing writes, client messages, or permission changes are implied.
- Every record needs a source, timestamp, and owner.
- `UNKNOWN` is a valid state when a connector or evidence is absent.
- The commander reviews the brief before the team turns it into cards.
- The brief is complete when the team can build the first read-only version without guessing at fields, owners, or sources.
