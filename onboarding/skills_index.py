#!/usr/bin/env python3
"""Read the repo's own skill->rung mapping, and see which ones you have installed.

`skills/README.md` already assigns every skill a rung (L1-L10). That table is
the single source of truth -- this module parses it rather than keeping a second
copy that would drift the moment someone adds a skill.

Detection is **presence-only**: we look for a skill directory in your agent
runtimes. We never read the contents of anything in your home directory.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKILLS_INDEX = REPO / "skills" / "README.md"

#: Where the different agent runtimes keep installed skills.
RUNTIME_SKILL_DIRS = (
    "~/.claude/skills",
    "~/.claude-max-1/skills",
    "~/.claude-max-2/skills",
    "~/.codex/skills",
    "~/.gemini/skills",
    "~/Sync/.agent-config/skills",
)

_LINK = re.compile(r"\[([a-z0-9][a-z0-9-]*)\]\((?:\./)?([a-z0-9-]+)/SKILL\.md\)")
_RUNG = re.compile(r"^L(\d{1,2})$", re.IGNORECASE)


def parse_index(index_path: Path = SKILLS_INDEX) -> dict[str, int]:
    """Return {skill-name: rung} parsed from the skills index tables.

    A row whose rung cell is not a clean ``L<n>`` is skipped rather than
    guessed at -- an unparseable rung must not silently become L1.
    """
    if not Path(index_path).exists():
        return {}
    mapping: dict[str, int] = {}
    for line in Path(index_path).read_text(encoding="utf-8").splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 2:
            continue
        link = _LINK.search(cells[0]) or (_LINK.search(cells[1]) if len(cells) > 1 else None)
        if not link:
            continue
        rung_match = _RUNG.match(cells[-1])
        if not rung_match:
            continue
        rung = int(rung_match.group(1))
        if 1 <= rung <= 10:
            mapping[link.group(2)] = rung
    return mapping


def repo_skills(repo: Path = REPO) -> set[str]:
    """Skill directories that actually exist in the repo."""
    skills_dir = Path(repo) / "skills"
    if not skills_dir.is_dir():
        return set()
    return {d.name for d in skills_dir.iterdir() if d.is_dir() and (d / "SKILL.md").exists()}


def installed_skills(runtime_dirs: tuple[str, ...] = RUNTIME_SKILL_DIRS) -> dict[str, str]:
    """{skill-name: where it was found}. Presence only -- contents are never read."""
    found: dict[str, str] = {}
    for raw in runtime_dirs:
        base = Path(raw).expanduser()
        if not base.is_dir():
            continue
        for entry in base.iterdir():
            try:
                is_skill = entry.is_dir() and (entry / "SKILL.md").exists()
            except OSError:
                continue
            if is_skill and entry.name not in found:
                found[entry.name] = raw
    return found


def by_rung(repo: Path = REPO, index_path: Path | None = None) -> dict[int, list[str]]:
    """{rung: [skill names in this repo at that rung]}."""
    mapping = parse_index(index_path or (Path(repo) / "skills" / "README.md"))
    present = repo_skills(repo)
    out: dict[int, list[str]] = {}
    for name, rung in sorted(mapping.items()):
        if name in present:
            out.setdefault(rung, []).append(name)
    return out


def status(repo: Path = REPO, runtime_dirs: tuple[str, ...] = RUNTIME_SKILL_DIRS) -> dict:
    """Full picture: what this repo offers per rung, and what you already run."""
    rungs = by_rung(repo)
    have = installed_skills(runtime_dirs)
    per_rung = {}
    for rung, names in rungs.items():
        got = [n for n in names if n in have]
        per_rung[rung] = {
            "available": names,
            "installed": got,
            "missing": [n for n in names if n not in have],
            "pct": round(100.0 * len(got) / len(names), 1) if names else 0.0,
        }
    return {
        "by_rung": per_rung,
        "installed_total": len([n for n in have if n in {s for v in rungs.values() for s in v}]),
        "available_total": sum(len(v) for v in rungs.values()),
        "any_runtime_found": bool(have),
    }


def missing_for_rung(rung: int, repo: Path = REPO, runtime_dirs=RUNTIME_SKILL_DIRS) -> list[str]:
    return status(repo, runtime_dirs)["by_rung"].get(rung, {}).get("missing", [])


if __name__ == "__main__":
    result = status()
    print(f"repo skills mapped to a rung: {result['available_total']}")
    print(f"installed on this machine:    {result['installed_total']}")
    for rung in sorted(result["by_rung"]):
        row = result["by_rung"][rung]
        print(f"  L{rung:<3} {len(row['installed'])}/{len(row['available'])}  ({row['pct']}%)")
