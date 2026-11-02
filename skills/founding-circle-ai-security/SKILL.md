---
name: founding-circle-ai-security
description: Operate a measurable security baseline for AI agents.
version: 0.1.0
author: JD, Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [security, agents, governance, audit]
    related_skills: []
---

# Founding Circle AI Security Skill

Use this workflow to inventory AI-agent skills and tools, assign least-privilege controls, collect evidence, and report readiness across Hermes, Claude Code, Gemini, Cursor, Codex, and Board. This skill creates governance artifacts; it does not replace runtime sandboxing, secret brokering, network enforcement, or human approval.

## When to Use

- onboarding an agent, skill, connector, model, or browser workflow
- reviewing a skill update or dependency change
- preparing a security readiness review
- responding to a suspected prompt-injection, credential, or tool-abuse event

Do not use this as proof that a control is enforced. Verify enforcement in the runtime.

## Prerequisites

- The accompanying security register, dashboard, and templates from the kit.
- Access to the repository, deployment, logs, and owners being assessed.

## Procedure

1. **Inventory.** Record every executable skill, tool, connector, model/provider, secret class, browser profile, memory store, and execution environment. Completion: no unknown production item remains.
2. **Classify.** Assign an owner, data classification, risk tier, capability set, source URI, version, and artifact hash. Completion: every item has all fields populated.
3. **Gate skills.** Review provenance, dependencies, shell/filesystem/network/browser/connector behavior, and external instructions. Completion: critical findings block approval; accepted exceptions have an owner and expiry.
4. **Enforce boundaries.** Verify deny-by-default permissions, isolated execution, scoped secrets, egress controls, connector write approval, and protected memory/configuration. Completion: attach evidence for each control; do not accept policy text alone.
5. **Instrument.** Verify logs for model calls, tool calls, approvals, denials, secret leases, routing, memory writes, and policy changes. Completion: replay one complete action timeline.
6. **Test.** Run prompt-injection, malicious-skill update, secret-exfiltration, connector-abuse, memory-poisoning, and sandbox-boundary tests in a disposable environment. Completion: record pass/fail, evidence, and remediation owner.
7. **Report.** Update the register, open remediation items, and open the dashboard. Completion: status, due dates, evidence links, and next actions are visible.
8. **Respond.** If compromise is suspected, disable the skill, revoke credentials, preserve logs, identify affected data, and document recovery. Completion: record timestamps for containment and revocation.
9. **Triage host input anomalies safely.** On macOS, collect `memory_pressure`, top processes, launch agents/daemons, system extensions, Bluetooth/USB HID inventory, accessibility settings, and recent `keyboardservicesd`/WindowServer/XProtect logs before terminating anything. Distinguish memory pressure from input faults: healthy free memory does not explain phantom keystrokes. Restart only the input service (`killall -TERM keyboardservicesd`) and terminate an optional high-resource app only when its identity and user impact are clear; never mass-kill system processes or persistence entries. Isolate external HID devices one at a time, then compare logs for keyboard events versus multitouch/button events. Completion: state the evidence-backed suspected source, actions taken, and remaining hardware/software test.

## Minimum control baseline

- 100% of executable skills registered, owned, versioned, and hash-pinned.
- Zero ambient host credentials.
- Default-deny network egress with logging.
- Isolated terminal/browser workers.
- Human approval for destructive or external writes.
- Append-only, attributed memory changes.
- Tamper-evident audit logs.
- Global kill switch tested quarterly.

## Output

Maintain `security-register.json`, evidence links, exception records, and a dated dashboard export. Use the included validator before sharing.

## Pitfalls

- A Git repository is not proof of trust.
- A hash proves identity, not benign behavior.
- A prompt is not an access-control boundary.
- A container with host sockets or broad mounts is not an adequate sandbox.
- Read-only data can still contain secrets or prompt injection.
- Logging without alerting and response ownership is weak assurance.

## Verification

Run the kit's register validator. Confirm the dashboard loads the same JSON and that every control marked `complete` has at least one evidence link.
