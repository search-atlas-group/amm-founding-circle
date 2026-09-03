#!/usr/bin/env python3
"""Agent memory starter kit — cross-platform uninstaller (macOS, Linux, Windows).

    python3 uninstall.py [--claude-dir DIR] [--brain-dir DIR] [--collection NAME]

Removes: the two hook scripts, their settings.json entries, the brain-search skill, the
/remember command, and the refresh script.
Leaves alone: your notes folder, and the qmd collection.
"""
import argparse
import json
import os
import sys
from pathlib import Path

KIT = Path(__file__).resolve().parent
sys.path.insert(0, str(KIT))

import kitlib  # noqa: E402
from kitlib import say  # noqa: E402


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--claude-dir", default=None)
    p.add_argument("--brain-dir", default=None)
    p.add_argument("--collection", default=None)
    return p.parse_args(argv)


def remove_hook_entries(settings, needle):
    """Drop every hook entry whose command mentions `needle`, whatever its arguments.

    Matching on the script name rather than the exact command string means an install done
    with a different interpreter, notes folder or collection is still cleaned up.
    """
    if not settings.exists():
        return 0
    try:
        data = json.loads(settings.read_text(encoding="utf-8") or "{}")
    except (OSError, json.JSONDecodeError):
        say("could not read %s — left untouched" % settings)
        return 0
    if not isinstance(data, dict):
        return 0
    hooks = data.get("hooks")
    if not isinstance(hooks, dict):
        return 0

    removed = 0
    for event in list(hooks):
        matchers = hooks.get(event)
        if not isinstance(matchers, list):
            continue
        for m in matchers:
            inner = m.get("hooks") if isinstance(m, dict) else None
            if not isinstance(inner, list):
                continue
            keep = [h for h in inner
                    if not (isinstance(h, dict) and needle in str(h.get("command", "")))]
            removed += len(inner) - len(keep)
            m["hooks"] = keep
        hooks[event] = [m for m in matchers
                        if not (isinstance(m, dict) and m.get("hooks") == []
                                and set(m) <= {"hooks", "matcher"})]
        if not hooks[event]:
            hooks.pop(event, None)
    if not hooks:
        data.pop("hooks", None)
    if removed:
        text = json.dumps(data, indent=2) + "\n"
        json.loads(text)
        tmp = settings.with_suffix(settings.suffix + ".tmp")
        tmp.write_text(text, encoding="utf-8", newline="\n")
        os.replace(str(tmp), str(settings))
    return removed


def main(argv=None):
    args = parse_args(argv)
    env = os.environ
    claude_dir = (Path(args.claude_dir).expanduser() if args.claude_dir
                  else kitlib.claude_config_dir(env))
    brain_dir = (Path(args.brain_dir).expanduser() if args.brain_dir
                 else kitlib.default_notes_dir(env))
    collection = args.collection or env.get("BRAIN_COLLECTION") or "brain"

    print("Agent memory starter kit — removing from %s" % claude_dir)
    settings = claude_dir / "settings.json"
    n = remove_hook_entries(settings, "qmd-recall-hook.py")
    n += remove_hook_entries(settings, "session-handoff-hook.py")
    say("removed %d hook entr%s from settings.json" % (n, "y" if n == 1 else "ies"))

    for rel in ("hooks/qmd-recall-hook.py", "hooks/session-handoff-hook.py",
                "hooks/refresh-brain.py", "hooks/refresh-brain.sh",
                "skills/brain-search/SKILL.md", "commands/remember.md"):
        p = claude_dir / rel
        try:
            p.unlink()
            say("removed %s" % p)
        except FileNotFoundError:
            pass
        except OSError as e:
            say("could not remove %s (%s)" % (p, e))
    try:
        (claude_dir / "skills" / "brain-search").rmdir()
    except OSError:
        pass

    print("""
Left alone on purpose:
  %(brain)s   your notes
  qmd collection '%(collection)s' — drop it yourself with: qmd collection remove %(collection)s

If you scheduled refresh-brain.py with cron, launchd or Task Scheduler, remove that entry
yourself. Restart Claude Code to drop the hook from running sessions.""" % {
        "brain": brain_dir, "collection": collection})
    return 0


if __name__ == "__main__":
    sys.exit(main())
