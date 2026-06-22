# Security Radar — harden your agentic setup

A small kit to make your agentic setup measurably more secure: a skill that audits your own machine, plus two reference handouts. Built for the AMM cohort.

The shift it's built around: static "scan before you install" is necessary but not sufficient. A package you vetted in March can be compromised in May (the npm worms of 2025 proved it). So you also need to **watch the surface you already run**. That's what `security-radar` does.

---

## What's in here

```
security-radar/
  SKILL.md            ← the Claude Code skill
  security-radar.py   ← the scanner (Python stdlib only — no installs)
handouts/
  active-threats.html / .pdf      ← the 7 attack patterns hitting agencies now
  owasp-cheatsheet.html / .pdf    ← OWASP LLM + Web Top 10, mapped to what you run
```

## Install (2 minutes)

1. Copy the `security-radar/` folder into your skills directory:
   ```
   cp -R security-radar ~/.claude/skills/security-radar
   ```
2. That's it. Claude Code will pick up the skill. Ask it: **"run security-radar on my setup."**

Prefer the command line? Just run the script directly:
```
python3 ~/.claude/skills/security-radar/security-radar.py
```

## What it checks (read-only — it changes nothing)

| Surface | What it looks for | OWASP |
|---|---|---|
| Installed skills | remote-pipe-to-shell, eval of fetched code, hardcoded creds | LLM05 Supply Chain |
| MCP servers | 3rd-party / remote servers that may hold your auth tokens | LLM07 Insecure Plugin Design |
| Permissions | `bypassPermissions`, wildcard allow rules | LLM08 Excessive Agency / A01 |
| Dependencies | `npm audit` + OSV.dev for known-vulnerable versions | LLM05 / A06 Vulnerable Components |

You get a posture brief with an overall rating (CLEAN / CARE / QUARANTINE / REJECT), the findings worst-first, and a concrete fix for each. A copy is saved to `~/security-radar-report-<date>.md`.

## Make it stick (this is the point)

- **Run it weekly.** The threat surface moves even when your code doesn't.
- **Designate one owner** per team to run it and triage findings.
- **Roll it out to your team** so nobody runs unvetted code on a client machine.

## The two tools, together

- **`/security-scan`** — vet a repo *before* you install it (point-in-time).
- **`security-radar`** — audit the surface you *already* run (continuous).

Use both. Scan on the way in, radar on a cadence.
