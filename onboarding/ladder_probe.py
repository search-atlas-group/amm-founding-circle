#!/usr/bin/env python3
"""Score a member's system against the Agentic Ladder.

We do not score you against our tooling. Each rung is a set of **objectives**,
and each objective can be satisfied several genuinely different ways (see
``objectives.py``). Your architecture is translated into the ladder; whatever
shape you built it in, if the capability is there, it counts.

Three numbers come out:

    reach   -- the highest rung you can climb to from the bottom
    floor   -- the highest rung with nothing broken beneath it
    system  -- 0-100, how developed the whole thing is, weighting higher rungs

``system`` is the headline score. It rewards both **depth** (a solid foundation)
and **height** (capabilities further up), so a member with a rock-solid
Foundation scores respectably while someone with one flashy rung-9 trick and
nothing underneath does not.

Privacy: presence-only, no network calls. See ``probes.py``.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import objectives as obj_mod
import skills_index
from objectives import RUNG_GOALS, RUNG_NAMES, TIERS  # re-exported for report.py

ANSWERS = Path(__file__).resolve().parent / ".answers.json"
REPO = Path(__file__).resolve().parent.parent

MET, UNMET, ASK = "met", "unmet", "ask"
EVIDENCED = ("solid", "partial", "unconfirmed")

#: A rung is called solid at this share of its objective weight, partial above zero.
SOLID_AT = 0.85
PARTIAL_AT = 0.34


def evaluate(answers: dict | None = None, repo: Path = REPO) -> dict:
    """Run every objective against this machine."""
    a = answers or {}
    facts = obj_mod.gather()
    installed = set(skills_index.installed_skills())
    sk = skills_index.status(repo)

    results: dict[int, list[dict]] = {r: [] for r in range(1, 11)}
    for objective in obj_mod.build(installed, sk):
        matched: list[str] = []
        detail = ""
        for signature in objective.signatures:
            try:
                ok, found = signature.detect(facts)
            except Exception:  # a broken probe must never break the scan
                ok, found = False, ""
            if ok:
                matched.append(signature.label)
                detail = detail or found

        if matched:
            status = MET
        elif objective.ask is not None:
            answered = a.get(objective.id)
            if answered is True:
                status, detail = MET, "you confirmed this"
                matched = ["your own confirmation"]
            elif answered is False:
                status, detail = UNMET, "you said not yet"
            else:
                status, detail = ASK, objective.ask
        else:
            status = UNMET

        results[objective.rung].append({
            "id": objective.id,
            "rung": objective.rung,
            "goal": objective.goal,
            "why": objective.why,
            "weight": objective.weight,
            "status": status,
            "matched": matched,
            "detail": detail,
            "ways": [s.label for s in objective.signatures],
            "ask": objective.ask,
            "suggestion": objective.suggestion,
            "skill": objective.skill,
        })

    return {"rungs": results, "skills": sk, "facts_summary": {
        "clis": facts["clis"], "scheduled_jobs": len(facts["jobs"]),
        "mcp": len(facts["mcp"]), "repos": len(facts["repos"])}}


def rung_score(items: list[dict]) -> dict:
    """Weighted score for one rung, plus the plain-English caption for its card.

    Two percentages, deliberately:

    ``pct``     progress against what we have actually asked you. Unanswered
                questions are excluded, because you must never be marked down
                for something nobody asked. This drives the card's status.
    ``earned``  points against every objective on the rung. Unanswered questions
                count as not-yet-earned. This drives the score, because an
                unconfirmed capability is not a demonstrated one.
    """
    total = sum(i["weight"] for i in items) or 1
    met = sum(i["weight"] for i in items if i["status"] == MET)
    unanswered = [i for i in items if i["status"] == ASK]
    askable = sum(i["weight"] for i in unanswered)

    scored_total = (total - askable) or 1
    pct = round(100.0 * met / scored_total, 1)
    earned = round(100.0 * met / total, 1)

    if not items or (met == 0 and askable == total):
        status = "unknown"
    elif pct >= SOLID_AT * 100:
        status = "unconfirmed" if unanswered else "solid"
    elif met > 0:
        status = "partial"
    else:
        status = "gap"

    have = [i["goal"] for i in items if i["status"] == MET]
    missing = [i["goal"] for i in items if i["status"] == UNMET]
    caption = {
        "solid": "everything this rung needs is in place",
        "unconfirmed": f"looks complete — {len(unanswered)} question(s) left for you",
        "partial": f"{len(have)} of {len(items)} capabilities in place",
        "gap": "nothing here yet — this rung is not started",
        "unknown": "we have not asked you about this rung yet",
    }[status]

    return {"pct": pct, "earned": earned, "status": status, "caption": caption,
            "met": len(have), "total": len(items),
            "unanswered": [i["id"] for i in unanswered],
            "missing": missing}


def climb_reach(statuses: dict[int, str], tolerate: int = 1) -> int | None:
    """The highest rung you can *climb* to, not the highest you touch.

    A hole underneath you can be stepped over. Two empty rungs in a row is a
    chasm, and anything past it is not a rung you operate at. Without this, one
    passing check high up hands a beginner a rung-9 headline.
    """
    reach, missing_run = None, 0
    for rung in range(1, 11):
        if statuses.get(rung) in EVIDENCED:
            reach, missing_run = rung, 0
        else:
            missing_run += 1
            if missing_run > tolerate:
                break
    return reach


def system_score(scores: dict[int, dict]) -> int:
    """0-100 for how developed the whole system is.

    Two rules, both load-bearing:

    * **Higher rungs are worth more.** A rung contributes in proportion to its
      number, so building upward counts for more than polishing the bottom.
    * **A rung only banks what its foundation supports.** Each rung's
      contribution is multiplied by how solid everything beneath it is. Without
      this, one impressive capability at rung 9 with an empty ladder underneath
      outscores a genuinely solid Foundation -- which is precisely the fragile
      architecture the ladder exists to expose.

    So the hollow top scores near zero, and the only route to a high number is
    to actually build up from the bottom.
    """
    earned_total = 0.0
    for rung in range(1, 11):
        earned = scores[rung]["earned"] / 100.0
        below = [scores[r]["earned"] / 100.0 for r in range(1, rung)]
        support = 1.0 if not below else sum(below) / len(below)
        earned_total += earned * support * rung
    return round(100.0 * earned_total / sum(range(1, 11)))


def tier_progress(scores: dict[int, dict]) -> dict[str, int]:
    """Completion per tier, ungated by the rungs above it.

    The system score is deliberately steep -- three solid rungs out of ten is a
    small number, because it is a small share of the ladder. That is honest, but
    on its own it reads as failure to someone who has genuinely finished the
    Foundation. Tier progress is the companion number: it says "Foundation 100%"
    to the person who earned it, while the system score keeps the whole ladder
    in view.
    """
    out: dict[str, int] = {}
    for tier in ("Foundation", "Scale", "System", "Autonomy"):
        rungs = [r for r in range(1, 11) if TIERS[r] == tier]
        out[tier] = round(sum(scores[r]["earned"] for r in rungs) / len(rungs))
    return out


def assess(result: dict) -> dict:
    scores = {r: rung_score(result["rungs"][r]) for r in range(1, 11)}
    statuses = {r: scores[r]["status"] for r in range(1, 11)}
    reach = climb_reach(statuses)

    floor = 0
    for rung in range(1, 11):
        if statuses.get(rung) == "solid":
            floor = rung
        else:
            break

    span = range(1, (reach or 0) + 1)
    gaps = sorted(r for r in span if statuses.get(r) in ("gap", "partial"))
    unconfirmed = sorted(r for r in span if statuses.get(r) == "unconfirmed")
    integrity = None
    if reach:
        integrity = round(sum(scores[r]["earned"] for r in span) / reach, 1)

    next_rung = gaps[0] if gaps else min((reach or 0) + 1, 10)
    todo = [i for i in result["rungs"].get(next_rung, []) if i["status"] != MET]

    return {
        "scores": scores,
        "statuses": statuses,
        "reach": reach,
        "floor": floor or None,
        "gaps": gaps,
        "unconfirmed": unconfirmed,
        "foundation_integrity_pct": integrity,
        "system_score": system_score(scores),
        "tier_progress": tier_progress(scores),
        "current_rung": reach or 1,
        "next_rung": next_rung,
        "next_actions": todo,
        "climbing": not gaps,
        "unanswered": [i["id"] for items in result["rungs"].values()
                       for i in items if i["status"] == ASK],
    }


# --- answers ---------------------------------------------------------------


def load_answers(path: Path = ANSWERS) -> dict:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_answers(answers: dict, path: Path = ANSWERS) -> None:
    Path(path).write_text(json.dumps(answers, indent=2) + "\n", encoding="utf-8")


def ask_questions(result: dict, answers: dict) -> dict:
    pending = [(i["id"], i["ask"]) for items in result["rungs"].values()
               for i in items if i["status"] == ASK]
    if not pending:
        print("Nothing to ask — the scan settled everything it could.")
        return answers
    print(f"\n{len(pending)} thing(s) a filesystem scan cannot see.")
    print("Answer honestly — an inflated rung only buys you worse coaching. Enter to skip.\n")
    for key, question in pending:
        try:
            reply = input(f"  {question} [y/n/skip] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\nstopped — answers so far are saved.")
            break
        if reply.startswith("y"):
            answers[key] = True
        elif reply.startswith("n"):
            answers[key] = False
    save_answers(answers)
    return answers


# Backwards-compatible aliases used elsewhere in the flow.
probe = evaluate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ask", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    answers = load_answers()
    result = evaluate(answers)
    if args.ask:
        answers = ask_questions(result, answers)
        result = evaluate(answers)
    v = assess(result)

    if args.json:
        print(json.dumps({"result": result, "assessment": v}, indent=2, default=str))
        return 0

    print(f"System score: {v['system_score']}/100")
    print("  " + "  ".join(f"{t} {p}%" for t, p in v["tier_progress"].items()))
    print(f"Operating at rung {v['current_rung']} — {RUNG_NAMES[v['current_rung']]} "
          f"({TIERS[v['current_rung']]})")
    print(f"  reach {v['reach'] or '-'}   defensible floor {v['floor'] or '-'}   "
          f"foundation {v['foundation_integrity_pct'] or '-'}%")
    if v["gaps"]:
        print(f"  real holes underneath you: rungs {v['gaps']}")
    if v["unconfirmed"]:
        print(f"  unconfirmed (not asked yet): rungs {v['unconfirmed']}")

    label = "Climb to" if v["climbing"] else "Fix first"
    print(f"\n{label}: rung {v['next_rung']} — {RUNG_NAMES[v['next_rung']]}")
    print(f"  Goal: {RUNG_GOALS[v['next_rung']]}")
    for item in v["next_actions"]:
        mark = "?" if item["status"] == ASK else " "
        print(f"  [{mark}] {item['goal']} — {item['suggestion']}")
    if v["unanswered"]:
        print(f"\n{len(v['unanswered'])} question(s) unanswered — run with --ask.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
