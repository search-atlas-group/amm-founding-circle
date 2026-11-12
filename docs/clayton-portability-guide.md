# Founding Circle portability guide

This guide covers the onboarding audit and its boundaries. Upgrade a clone with
`git pull --ff-only`, then rerun `python3 -m pytest onboarding/test_onboarding.py onboarding/test_clayton_portability.py -q`.

Windows: run `.\onboarding\onboard.ps1 -NoOpen -NoHermes -AnswersFile .\answers.json`.
The same noninteractive contract works on macOS/Linux: `./onboarding/onboard.sh
--no-open --no-hermes --answers-file ./answers.json`. Answers are objective IDs
mapped to true/false; `--answer 9.proven=true` is repeatable. Native Windows
execution is covered in Windows CI; it is not claimed from a non-Windows shell.

The Search Atlas claude.ai connector is cloud state. The local audit reports it
as unknown and asks for manual confirmation; it never infers “not connected.”
Project allowlists, project skills, grounded run records, and real package test
scripts count. Dummy echo/true scripts do not. Missing evidence is not the same
as evidence of absence.

Agent usage keeps provider quota and local cost separate: use built-in `/usage`
where supported, and the bundled ledger script for cross-provider token counts.
It never converts tokens into remaining subscription capacity. The code-base map
is an on-demand, bounded navigation aid; existing docs and search remain primary.

Clayton's reported hours and unnamed unattended job are intake prompts, not
benchmarks. Supply measured before/after time and a named run with completion
evidence before treating them as outcomes.
