#!/usr/bin/env bash
# ============================================================================
#  THIS IS THE ONE FILE YOU EDIT.
#
#  Copy it to my-job.sh, then write — in plain English, between the two markers
#  below — the ONE recurring thing you want your agent to do overnight.
#
#  The runner reads the text between the markers and hands it to your agent,
#  pointed at the folder you scheduled it against. Keep it to a single, clear
#  job. When it's solid and you trust it, make a second copy for a second job —
#  don't cram everything into one.
#
#  Tips for a good job:
#   - Name the folder/repo it should look at (or schedule it inside that folder).
#   - Say what "done" looks like ("leave me a one-page brief", "draft the posts").
#   - It runs READ-ONLY by default. If it genuinely needs to write files, the
#     runner must be started with --allow-writes (a deliberate opt-in).
# ============================================================================

# --- JOB ---
Sweep this folder for anything that changed since yesterday. Read the notes,
tasks, and any client files here. Then leave me a one-page morning brief in
plain English:
  - the 3 things that most need my attention today, most important first
  - anything that looks broken, stuck, or overdue
  - one suggested next action for each

Do not edit any files. Just read and report.
# --- END JOB ---

# You can keep normal shell setup below the markers if you like — the runner
# ignores everything outside the JOB block. (The runner does not execute this
# script; it only extracts the instruction above.)
