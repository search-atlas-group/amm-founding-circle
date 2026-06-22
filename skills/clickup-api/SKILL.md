---
name: clickup-api
description: ClickUp v3 API conventions, channel/DM creation rules, thread reply endpoints, and the company-wide 🧞 emoji prefix requirement for any Claude-authored ClickUp message. Use when sending ClickUp messages, creating channels, replying to threads, or scripting against the ClickUp API.
triggers:
- clickup message
- clickup channel
- send to clickup
- clickup dm
- clickup api
- clickup mcp
- reply in clickup
- post in clickup
- clickup thread reply
---

# clickup-api

ClickUp v3 quirks the team has been bitten by. Read before sending any message, creating any channel, or calling any ClickUp endpoint.

## Hard rules (NEVER violate)

### Never create public channels
**Forbidden:** `POST /chat/channels` — creates a public channel visible to the entire 50+ person workspace. This has caused real noise/cleanup incidents.

**Required pattern:** `POST /chat/channels/direct_message` with `user_ids` — creates a private DM (1 user) or group DM (2+ users). All messaging to teammates routes through DMs, never new public channels.

### Always prefix team-facing messages with 🧞
Any ClickUp message sent to teammates via Claude — DM, group DM, thread reply, or channel post — MUST start with the 🧞 emoji. Lets recipients identify Claude-authored messages at a glance. Applies to all scripts, MCP tools, and direct API calls. No exceptions.

## Endpoint reference

### DM creation
- `POST /chat/channels/direct_message` body: `{"user_ids": [<numeric>, ...]}`
- 1 user_id → private 1:1 DM
- 2+ user_ids → group DM
- Returns channel ID — then `POST /chat/channels/{id}/messages` to send.

### Thread replies
- Reply to a message: `POST /messages/{message_id}/replies`
- **NOT** the channel endpoint. A common mistake is posting back to the channel as a new top-level message instead of as a reply on the thread.

### Channel listing
- `GET /chat/channels` — paginated. Use the `cursor` from `next_cursor` field for the next page. `total_count` field returns the page size, not the full count — pages have `has_more`.

### DM creation fallback (auth-scoped failure recovery)
If `POST /chat/channels/direct_message` returns 401/403 (the configured token may lack v3 chat-write scope), DO NOT block. Instead:
1. List channels via `clickup_get_chat_channels`.
2. Filter to `type=DM`.
3. Probe each candidate's first few messages via `clickup_get_chat_channel_messages`, looking for the target user_id as sender.
4. Reuse the existing DM channel.

Reference incident: an existing teammate DM was identified this way on 2026-05-21 after v3 token auth failed.

## Roster hygiene

The `team_roster.json` file contains stale entries for people who have left the company. Before tagging, mentioning, or sending outbound messages:
1. Cross-check against current ClickUp workspace members (`clickup_get_workspace_members` or `clickup_resolve_assignees`).
2. Filter out likely-departed members before any outbound action.
3. Departures happen in waves (15+ in one day on recent offboarding) — assume roster is stale unless freshly synced.

## Partner channels — skip the noise

Do NOT assume a channel owner needs to reply to partner-channel messages unless
they are directly tagged. Partner-channel messages should usually be handled by
the CSM/support team. Filter untargeted partner-channel pings out of any triage
workflow.

## Reference

Full endpoint details in `~/.claude/reference/clickup-api.md`.
