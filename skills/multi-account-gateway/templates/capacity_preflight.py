#!/usr/bin/env python3
"""Capacity preflight for an always-on agent run.

This is a READ-ONLY CHECK, not a router. It confirms that an unattended run is
configured the ToS-clean way BEFORE you walk away from it:

  1. a budgeted API key is present (the recommended lane),
  2. a fallback route exists (so one provider's bad night doesn't kill the run),
  3. and it prints the one capacity pattern that gets accounts banned, so it's
     in front of you every single time.

It NEVER pools, rotates, or blends accounts. It reads environment variables,
tells you what it found, and exits. That's the whole job.

Usage:
    python3 capacity_preflight.py

Reads these environment variables (see gateway.env.example):
    PRIMARY_API_KEY        the budgeted, metered API key your runner uses (required)
    PRIMARY_PROVIDER       a label for your primary provider, e.g. "anthropic" (optional)
    PRIMARY_SPEND_CAP_SET  "yes" once you've set a monthly cap in the provider console
    FALLBACK_API_KEY       a second provider's key OR
    FALLBACK_CLI           a local model CLI command name (e.g. a direct-CLI fallback)

Exit codes:
    0  ready to walk away (budgeted key + a fallback route both present)
    1  not ready (missing a budgeted key or any fallback route)

No third-party dependencies. Standard library only.
"""

from __future__ import annotations

import os
import shutil
import sys

# The red line. Printed on every run so it is never out of sight.
TOS_RED_LINE = (
    "REMINDER: More capacity comes from raising your API budget, staggering jobs, "
    "or adding a real second provider. It NEVER comes from pooling personal "
    "subscription logins behind a shared proxy/relay — that is a named, enforced "
    "Anthropic ToS violation and gets EVERY account in the pool banned. Do not do it."
)


def _present(value: str | None) -> bool:
    """A value counts as present only if it's a non-empty, non-placeholder string."""
    if not value:
        return False
    stripped = value.strip()
    if not stripped:
        return False
    # Reject obvious leftover placeholders from the example env file.
    placeholder_markers = ("your-", "changeme", "<", "example", "replace-me")
    lowered = stripped.lower()
    return not any(marker in lowered for marker in placeholder_markers)


def check_primary() -> tuple[bool, str]:
    """A budgeted API key is the recommended lane. It must be present."""
    key = os.environ.get("PRIMARY_API_KEY")
    provider = os.environ.get("PRIMARY_PROVIDER", "").strip() or "your provider"
    if _present(key):
        return True, f"Primary: budgeted API key found for {provider}."
    return False, (
        "Primary: NO budgeted API key found (PRIMARY_API_KEY). This is the "
        "recommended lane — a metered key with a spending cap you set. Add one "
        "before running unattended."
    )


def check_spend_cap() -> tuple[bool, str]:
    """We can't read the provider's billing console, so we self-attest the cap.

    A cap is what makes walking away safe: a runaway job hits it and STOPS,
    instead of surprising you with a bill. This check just makes sure you've
    consciously confirmed you set one.
    """
    attested = os.environ.get("PRIMARY_SPEND_CAP_SET", "").strip().lower()
    if attested in ("yes", "true", "1"):
        return True, "Spend cap: confirmed set in the provider console."
    return False, (
        "Spend cap: NOT confirmed. Set a monthly cap in your provider's billing "
        "console, then set PRIMARY_SPEND_CAP_SET=yes. This is the single step "
        "that makes an unattended run safe to leave."
    )


def check_fallback() -> tuple[bool, str]:
    """A fallback route: a second provider's key, or a local model CLI.

    Either satisfies the 'keep working when one source is busy' requirement.
    """
    fallback_key = os.environ.get("FALLBACK_API_KEY")
    fallback_cli = os.environ.get("FALLBACK_CLI", "").strip()

    if _present(fallback_key):
        return True, "Fallback: a second provider API key is configured."

    if fallback_cli:
        if shutil.which(fallback_cli):
            return True, f"Fallback: local CLI '{fallback_cli}' found on PATH."
        return False, (
            f"Fallback: FALLBACK_CLI is set to '{fallback_cli}' but that command "
            "isn't on your PATH. Install it or fix the name."
        )

    return False, (
        "Fallback: NO fallback route found. Add either a FALLBACK_API_KEY (a "
        "second provider) or a FALLBACK_CLI (a local model CLI). Without one, a "
        "single provider having a bad night kills the whole run."
    )


def main() -> int:
    print("=" * 72)
    print("  Capacity preflight — is this unattended run safe to leave?")
    print("=" * 72)
    print()

    checks = [
        check_primary(),
        check_spend_cap(),
        check_fallback(),
    ]

    for ok, message in checks:
        marker = "PASS" if ok else "FAIL"
        print(f"  [{marker}] {message}")

    print()
    print("-" * 72)
    print(TOS_RED_LINE)
    print("-" * 72)
    print()

    # Ready to walk away requires a budgeted primary key AND a fallback route.
    # The spend cap is strongly urged but self-attested, so it's a warning, not a hard block.
    primary_ok = checks[0][0]
    cap_ok = checks[1][0]
    fallback_ok = checks[2][0]

    if primary_ok and fallback_ok:
        if not cap_ok:
            print(
                "  NEARLY READY: budgeted key + fallback are in place, but you have "
                "not confirmed a spending cap. Set one before you trust a long run."
            )
        else:
            print("  READY: budgeted key + spend cap + fallback all in place. Walk away.")
        return 0

    print(
        "  NOT READY: fix the FAIL lines above. You need at least a budgeted API "
        "key AND a fallback route before running unattended."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
