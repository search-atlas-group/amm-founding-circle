# agency-morning-brief

Wake up to a decision-ready day. Your agent sweeps your own inbox, tasks, calendar,
and CRM, works out what you genuinely still owe (not what you already handled
somewhere else), drafts the replies, and leaves you one page to read over coffee.

Read `SKILL.md` for the full walkthrough and the one rule that makes it trustworthy
(Correlate before you Judge). This README is the copy-paste quickstart.

## Quickstart (run it once, by hand, this morning)

Say this to your agent:

> "Run my morning brief. Sweep my inbox, my tasks, my calendar, and my CRM from the
> last day. Before you flag anything, check the whole conversation across all my
> sources so you don't surface something I already handled. Then give me a one-page
> brief — what needs me today, most important first, with a draft reply where you
> can write one. Read-only: draft, don't send."

That's it. It reads, correlates, drafts, and leaves you `Morning Brief — <today>`.

## Make it run every morning by itself

This skill is the *job*. To fire it on a schedule, off your laptop, use the
**`host-your-agent`** skill: copy its `my-job.sh`, paste the line above into the
JOB block, and schedule it for 6am. Read the **`night-shift`** skill once — it's the
safety contract (time box, read-only-by-default, fails-loud) that setup runs under.

## The two safety rules that matter

- **Read-only until earned.** It drafts; it never sends or changes anything until
  you deliberately move it up the trust ladder, one action at a time. Day one is
  observe-only.
- **Capacity without the ban.** If you run it unattended, give it headroom on a
  **budgeted API key with a spending cap** (the recommended, predictable path). Do
  **not** pool multiple personal-subscription logins behind a proxy to fake capacity —
  that violates Anthropic's terms of service and gets accounts banned. Raise your API
  budget or stagger jobs instead.

## Optional: sanity-check a finished brief

```bash
python3 templates/check_brief.py path/to/morning-brief.md
```

Reads only that one file, writes nothing. It checks the brief ends with an honest
STATUS line and that the correlate-first numbers (`closed_as_already_handled`,
`waiting_on_others`) are actually being reported — the proof your agent did the hard
step instead of just listing signals.

## What's in here

| File | What it is |
|---|---|
| `SKILL.md` | The full walkthrough: the loop, the correlate-first rule, the locked rules, the trust ladder. |
| `templates/brief-format.md` | The one-page brief shape to hand your agent. |
| `templates/correlation-worksheet.md` | A checklist that forces "who has the ball?" before anything gets flagged. |
| `templates/check_brief.py` | Optional read-only linter for a finished brief's STATUS line. |
