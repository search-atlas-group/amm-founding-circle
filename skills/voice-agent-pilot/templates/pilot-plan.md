# Voice-agent pilot plan — fill privately

Status: DRAFT / APPROVED / BLOCKED

- Operator / engineering owner / reviewer: [roles or private names]
- Date, start/stop time, timezone: [fill]
- Purpose: read one synthetic test-session status by voice
- Lane: OFFLINE_REHEARSAL / HOSTED_STAGED / LOCAL_NO_TOOLS
- Source mode: SYNTHETIC_FIXTURE / separately approved LIVE_TEST_SESSION
- Authenticated user-to-session grant: [one opaque test ID; no spoken identity]
- Allowed function: get_pilot_session_status
- Denied: writes, commands, other sessions, raw transcripts, file access, production credentials
- Approvals: [processor/privacy, account owner, installs/downloads, reviewer]
- Spend ceiling/currency: [fill; no approval means no hosted launch]
- Connection cap: 30 minutes; idle cap: 60 seconds; tool timeout: 5 seconds
- Data processors and region; retention/training settings reviewed: [fill or UNKNOWN]
- Credential owner/storage/revocation path: [location name, never the value]
- Recording: OFF by default; synthetic transcript/tool trace only
- Evidence folder outside tracked repo: [fill]
- Evidence viewers and deletion date: [fill]
- Effective STT/LLM/TTS IDs, audio formats, starter commit and package versions: [fill]
- Pre-pilot config backup and owned process inventory: [fill]
- Thresholds: greeting ≤2s; answer first audio ≤3s; interruption ≤500ms; timeout notice ≤6s
- Stop immediately for: leaked data, wrong session, attempted write, runaway cost, endless lag, missing stop control
- Rollback owner and procedure reviewed: [fill]
- Operator approval / reviewer approval / time: [fill]

Do not upload filled plans or recordings without explicit sharing permission.
