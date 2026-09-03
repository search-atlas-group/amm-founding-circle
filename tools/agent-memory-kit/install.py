#!/usr/bin/env python3
"""Agent memory starter kit — cross-platform installer (macOS, Linux, Windows).

    python3 install.py [--brain-dir DIR] [--collection NAME] [--claude-dir DIR]
                       [--handoff-hook] [--skip-index]

Idempotent: safe to re-run. Writes nothing outside the notes folder and the Claude Code
config directory. settings.json is merged by merge_settings.py, which backs the file up and
JSON-validates the result before replacing it, so hooks you already have are preserved.
"""
import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

KIT = Path(__file__).resolve().parent
sys.path.insert(0, str(KIT))

import kitlib  # noqa: E402
from kitlib import say, step  # noqa: E402

TOTAL = 6


def parse_args(argv=None):
    p = argparse.ArgumentParser(add_help=True, description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--brain-dir", default=None, help="notes folder (default: ~/brain)")
    p.add_argument("--collection", default=None, help="qmd collection name (default: brain)")
    p.add_argument("--claude-dir", default=None,
                   help="Claude Code config dir (default: CLAUDE_CONFIG_DIR or ~/.claude)")
    p.add_argument("--handoff-hook", action="store_true",
                   help="also install the opt-in session-end handoff stub writer")
    p.add_argument("--skip-index", action="store_true",
                   help="register the collection but do not run the first index")
    return p.parse_args(argv)


def run_qmd(qmd, args, check=False):
    try:
        r = subprocess.run([qmd] + list(args), capture_output=True, text=True, timeout=900)
    except Exception as e:  # noqa: BLE001
        if check:
            raise SystemExit("  qmd %s failed to start: %s" % (" ".join(args), e))
        return 1, "", str(e)
    if check and r.returncode != 0:
        sys.stderr.write((r.stdout or "") + (r.stderr or ""))
        raise SystemExit("  qmd %s exited %d" % (" ".join(args), r.returncode))
    return r.returncode, r.stdout or "", r.stderr or ""


def collection_registered(qmd, name):
    rc, out, _ = run_qmd(qmd, ["collection", "list"])
    if rc != 0:
        return False
    for line in out.splitlines():
        for token in line.replace("\t", " ").split(" "):
            token = token.strip().strip("()[]:,")
            if token == name:
                return True
    return False


def merge_settings(settings, event, command, timeout=5, remove=False):
    cmd = [sys.executable, str(KIT / "merge_settings.py"), str(settings), event, command,
           "--timeout", str(timeout)]
    if remove:
        cmd.append("--remove")
    r = subprocess.run(cmd, capture_output=True, text=True)
    sys.stdout.write("".join("  %s\n" % l for l in (r.stdout or "").splitlines()))
    if r.returncode != 0:
        sys.stderr.write(r.stderr or "")
        raise SystemExit("  settings.json merge failed — nothing was changed")


def main(argv=None):
    args = parse_args(argv)
    env = os.environ

    claude_dir = (Path(args.claude_dir).expanduser() if args.claude_dir
                  else kitlib.claude_config_dir(env))
    brain_dir = (Path(args.brain_dir).expanduser() if args.brain_dir
                 else kitlib.default_notes_dir(env))
    collection = args.collection or env.get("BRAIN_COLLECTION") or "brain"

    print("Agent memory starter kit — installing")
    say("platform:   %s" % sys.platform)
    say("python:     %s" % sys.executable)
    say("config dir: %s" % claude_dir)
    say("notes dir:  %s" % brain_dir)
    say("collection: %s" % collection)

    # ------------------------------------------------------------ 1. qmd
    step("1/%d  search engine (qmd)" % TOTAL)
    qmd = kitlib.find_qmd(env)
    if qmd:
        say("found: %s" % qmd)
    else:
        npm = kitlib.find_npm(env)
        if npm:
            say("qmd not found — installing with npm ...")
            r = subprocess.run([npm, "i", "-g", "qmd"], text=True)
            qmd = kitlib.find_qmd(env) if r.returncode == 0 else None
        if not qmd:
            print()
            print(kitlib.npm_install_hint())
            print()
            say("Nothing has been installed. Re-run once qmd is on your PATH.")
            return 1
        say("installed: %s" % qmd)

    # ------------------------------------------------------------ 2. notes folder
    step("2/%d  notes folder" % TOTAL)
    if brain_dir.is_dir() and any(brain_dir.iterdir()):
        say("%s exists and is not empty — leaving your notes alone" % brain_dir)
    else:
        (brain_dir / "memory").mkdir(parents=True, exist_ok=True)
        shutil.copy2(KIT / "brain-template" / "README.md", brain_dir / "README.md")
        shutil.copy2(KIT / "brain-template" / "TEMPLATE.md", brain_dir / "TEMPLATE.md")
        for memo in sorted((KIT / "brain-template" / "memory").glob("*.md")):
            shutil.copy2(memo, brain_dir / "memory" / memo.name)
        say("created %s with the convention README, a template and 3 example memos" % brain_dir)

    # ------------------------------------------------------------ 3. index
    step("3/%d  index the notes as collection '%s'" % (TOTAL, collection))
    if collection_registered(qmd, collection):
        say("already registered")
    else:
        run_qmd(qmd, ["collection", "add", str(brain_dir), "--name", collection], check=True)
        say("registered %s" % brain_dir)
    if args.skip_index:
        say("first index skipped (--skip-index)")
    else:
        rc, out, err = run_qmd(qmd, ["update"])
        if rc != 0:
            sys.stderr.write(out + err)
            say("WARNING: 'qmd update' exited %d — search may be empty until it succeeds" % rc)
        else:
            say("indexed")

    # ------------------------------------------------------------ 4. hooks
    step("4/%d  pushed-recall hook" % TOTAL)
    hooks_dir = claude_dir / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    recall = hooks_dir / "qmd-recall-hook.py"
    shutil.copy2(KIT / "hooks" / "qmd-recall-hook.py", recall)
    make_executable(recall)
    say("installed %s" % recall)

    settings = claude_dir / "settings.json"
    if not settings.exists():
        settings.parent.mkdir(parents=True, exist_ok=True)
        settings.write_text("{}\n", encoding="utf-8")
    merge_settings(settings, "UserPromptSubmit",
                   kitlib.hook_command(recall, ["--collection", collection]))

    handoff = hooks_dir / "session-handoff-hook.py"
    if args.handoff_hook:
        shutil.copy2(KIT / "hooks" / "session-handoff-hook.py", handoff)
        make_executable(handoff)
        merge_settings(settings, "SessionEnd",
                       kitlib.hook_command(handoff, ["--brain-dir", str(brain_dir)]))
        say("session-end handoff stubs enabled")
    else:
        say("session-end handoff hook NOT installed (re-run with --handoff-hook to enable)")

    # ------------------------------------------------------------ 5. skill + command
    step("5/%d  skill and slash command" % TOTAL)
    (claude_dir / "skills" / "brain-search").mkdir(parents=True, exist_ok=True)
    (claude_dir / "commands").mkdir(parents=True, exist_ok=True)
    shutil.copy2(KIT / "skills" / "brain-search" / "SKILL.md",
                 claude_dir / "skills" / "brain-search" / "SKILL.md")
    shutil.copy2(KIT / "commands" / "remember.md", claude_dir / "commands" / "remember.md")
    say("installed the brain-search skill and the /remember command")

    # ------------------------------------------------------------ 6. refresh script
    step("6/%d  refresh script" % TOTAL)
    refresh = hooks_dir / "refresh-brain.py"
    tmpl = (KIT / "refresh.py").read_text(encoding="utf-8")
    tmpl = tmpl.replace("@@BRAIN_DIR@@", str(brain_dir)).replace("@@COLLECTION@@", collection)
    refresh.write_text(tmpl, encoding="utf-8")
    make_executable(refresh)
    say("installed %s" % refresh)

    print_next_steps(claude_dir, recall, refresh, collection)
    return 0


def make_executable(path):
    if kitlib.is_windows():
        return
    try:
        os.chmod(path, os.stat(path).st_mode | 0o111)
    except Exception:  # noqa: BLE001
        pass


def print_next_steps(claude_dir, recall, refresh, collection):
    py = sys.executable
    print("""
Done. Restart Claude Code so it picks up the hook, the skill and the command.

Verify search works:

    qmd search "migration backfill non-null column" -c %(collection)s -n 3

Verify the hook fires:

    "%(py)s" "%(recall)s" --collection %(collection)s --prompt "what did we decide about migrations that add a non-null column"

That prints one line of JSON containing "additionalContext" — exactly what is pushed into
the agent before it thinks. A vague prompt prints nothing, which is also correct.

Keep the index fresh by scheduling:

    "%(py)s" "%(refresh)s"

README.md has copy-pasteable cron, launchd and schtasks lines.""" % {
        "collection": collection, "py": py, "recall": recall, "refresh": refresh})


if __name__ == "__main__":
    sys.exit(main())
