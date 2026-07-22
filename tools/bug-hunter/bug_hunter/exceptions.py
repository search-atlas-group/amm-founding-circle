"""Known-exceptions matching.

Spec requirement: "Optional per-client known exceptions list so the same
intentional oddity doesn't get flagged every week." A member copies a
finding's ``key`` (printed in every report row) into their client's
``known_exceptions`` list in clients.yaml. On the next run that finding is
still detected (so we never silently lose the underlying fact) but is
marked ``suppressed=True`` and demoted out of the active findings list the
report leads with.

Matching rule, in order:
1. Exact match against the finding's full key.
2. Prefix match — an exception ending in ``*`` matches any key with that
   prefix, so a member can silence a whole category/location at once, e.g.
   ``"acme-co/tracking/*"``.
"""

from __future__ import annotations

from .models import Finding


def is_known_exception(finding_key: str, known_exceptions: list[str]) -> bool:
    for entry in known_exceptions:
        entry = entry.strip()
        if not entry:
            continue
        if entry.endswith("*"):
            if finding_key.startswith(entry[:-1]):
                return True
        elif finding_key == entry:
            return True
    return False


def apply_known_exceptions(findings: list[Finding], known_exceptions: list[str]) -> list[Finding]:
    """Return a new list with matched findings flagged ``suppressed=True``.

    Never mutates the input list in place; callers can diff before/after.
    """
    out: list[Finding] = []
    for f in findings:
        if is_known_exception(f.key, known_exceptions):
            out.append(
                Finding(
                    client=f.client,
                    category=f.category,
                    severity=f.severity,
                    title=f.title,
                    detail=f.detail,
                    location=f.location,
                    suggested_fix=f.suggested_fix,
                    key=f.key,
                    suppressed=True,
                )
            )
        else:
            out.append(f)
    return out
