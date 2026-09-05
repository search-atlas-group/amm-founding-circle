#!/usr/bin/env python3
"""Agent memory starter kit — self test.

    python3 test.py [--keep]

Two parts, both offline:

1. An end-to-end run against a throwaway home directory: install, assert every file and
   settings.json entry, fire the recall hook on a sample prompt and check it points at one
   of the example memos, run the refresh script, write a handoff stub, uninstall, and
   assert the notes folder survived. Your real config directory and notes are never
   touched.
2. Unit tests for the Windows-specific branches, driven by fake environments and a
   monkeypatched os.name / sys.platform, so the Windows logic is checked on any platform.

Prints PASS/FAIL per check and exits non-zero if anything failed.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest.mock as mock
from pathlib import Path

KIT = Path(__file__).resolve().parent
sys.path.insert(0, str(KIT))
import kitlib  # noqa: E402

CHECKS = []


def check(ok, label, detail=""):
    CHECKS.append(bool(ok))
    print("%s  %s" % ("PASS" if ok else "FAIL", label))
    if not ok and detail:
        for line in str(detail).strip().splitlines()[-20:]:
            print("        %s" % line)
    return bool(ok)


def skip(label):
    print("SKIP  %s" % label)


# ---------------------------------------------------------------- part 1: end to end
def sandbox_env(root, claude_dir):
    """An environment where qmd, Claude Code config and notes all live under `root`."""
    env = dict(os.environ)
    env["HOME"] = str(root)
    env["USERPROFILE"] = str(root)
    env["CLAUDE_CONFIG_DIR"] = str(claude_dir)
    env["XDG_CONFIG_HOME"] = str(root / ".config")
    env["XDG_CACHE_HOME"] = str(root / ".cache")
    env["XDG_DATA_HOME"] = str(root / ".local" / "share")
    for k in ("BRAIN_DIR", "BRAIN_COLLECTION", "BRAIN_MIN_SCORE", "BRAIN_MAX_HITS"):
        env.pop(k, None)
    return env


def settings_commands(settings, event):
    data = json.loads(Path(settings).read_text(encoding="utf-8"))
    out = []
    for m in data.get("hooks", {}).get(event, []):
        for h in m.get("hooks", []):
            out.append(h.get("command", ""))
    return out


def end_to_end(keep=False):
    root = Path(tempfile.mkdtemp(prefix="kit-selftest-"))
    claude_dir = root / ".claude"
    brain_dir = root / "brain"
    collection = "selftest-brain-%d" % os.getpid()
    env = sandbox_env(root, claude_dir)
    print("== end-to-end, throwaway home: %s\n" % root)

    try:
        r = subprocess.run(
            [sys.executable, str(KIT / "install.py"), "--brain-dir", str(brain_dir),
             "--claude-dir", str(claude_dir), "--collection", collection, "--handoff-hook"],
            capture_output=True, text=True, env=env, timeout=1800)
        if not check(r.returncode == 0, "install.py completed", r.stdout + r.stderr):
            print("\n== aborting: install failed, later checks would be meaningless")
            return

        # files
        recall = claude_dir / "hooks" / "qmd-recall-hook.py"
        handoff = claude_dir / "hooks" / "session-handoff-hook.py"
        refresh = claude_dir / "hooks" / "refresh-brain.py"
        settings = claude_dir / "settings.json"
        check(recall.is_file(), "recall hook copied")
        check(handoff.is_file(), "handoff hook copied (--handoff-hook)")
        check(refresh.is_file(), "refresh-brain.py generated")
        check(os.name == "nt" or os.access(recall, os.X_OK), "recall hook is executable")
        check((claude_dir / "skills" / "brain-search" / "SKILL.md").is_file(),
              "brain-search skill installed")
        check((claude_dir / "commands" / "remember.md").is_file(), "/remember installed")
        check((brain_dir / "README.md").is_file(), "notes README created")
        check((brain_dir / "TEMPLATE.md").is_file(), "notes TEMPLATE created")
        memos = sorted((brain_dir / "memory").glob("*.md"))
        check(len(memos) == 3, "3 example memos created (found %d)" % len(memos))

        # settings.json
        check(json.loads(settings.read_text(encoding="utf-8")) is not None,
              "settings.json is valid JSON")
        ups = settings_commands(settings, "UserPromptSubmit")
        cmd = next((c for c in ups if "qmd-recall-hook.py" in c), "")
        check(bool(cmd), "settings.json has the UserPromptSubmit entry", ups)
        check(sys.executable in cmd, "hook command uses an absolute interpreter path", cmd)
        check(str(recall) in cmd, "hook command uses the absolute hook path", cmd)
        check("--collection %s" % collection in cmd or
              "--collection '%s'" % collection in cmd,
              "hook command passes the collection as an argument, not an env prefix", cmd)
        check("=" not in cmd.split(" ")[0], "hook command has no VAR=value shell prefix", cmd)
        se = settings_commands(settings, "SessionEnd")
        check(any("session-handoff-hook.py" in c for c in se),
              "settings.json has the SessionEnd entry", se)

        # re-running the installer must not duplicate the entry
        r2 = subprocess.run(
            [sys.executable, str(KIT / "install.py"), "--brain-dir", str(brain_dir),
             "--claude-dir", str(claude_dir), "--collection", collection, "--handoff-hook",
             "--skip-index"], capture_output=True, text=True, env=env, timeout=600)
        check(r2.returncode == 0, "install.py is re-runnable", r2.stdout + r2.stderr)
        ups2 = [c for c in settings_commands(settings, "UserPromptSubmit")
                if "qmd-recall-hook.py" in c]
        check(len(ups2) == 1, "re-install leaves exactly one recall entry (found %d)" % len(ups2))

        # S2-12(a): re-running with --collection when qmd already owns that name (here
        # pointing somewhere else entirely) must not hard-fail with a raw qmd dump.
        qmd_bin = kitlib.find_qmd(env)
        if qmd_bin:
            taken = collection + "-taken"
            other = root / "other-notes"
            (other).mkdir(parents=True, exist_ok=True)
            (other / "note.md").write_text("# other\n", encoding="utf-8")
            subprocess.run([qmd_bin, "collection", "add", str(other), "--name", taken],
                           capture_output=True, text=True, env=env, timeout=600)
            r3 = subprocess.run(
                [sys.executable, str(KIT / "install.py"), "--brain-dir", str(brain_dir),
                 "--claude-dir", str(claude_dir), "--collection", taken, "--skip-index"],
                capture_output=True, text=True, env=env, timeout=600)
            out3 = (r3.stdout or "") + (r3.stderr or "")
            check(r3.returncode == 0,
                  "installer is idempotent on an already-taken collection name (S2-12)", out3)
            check("Traceback" not in out3, "no raw traceback on the re-run", out3)
            subprocess.run([qmd_bin, "collection", "remove", taken],
                           capture_output=True, text=True, env=env, timeout=300)
            # put settings back on the real collection for the checks that follow
            subprocess.run(
                [sys.executable, str(KIT / "install.py"), "--brain-dir", str(brain_dir),
                 "--claude-dir", str(claude_dir), "--collection", collection,
                 "--handoff-hook", "--skip-index"],
                capture_output=True, text=True, env=env, timeout=600)
            cmd = next((c for c in settings_commands(settings, "UserPromptSubmit")
                        if "qmd-recall-hook.py" in c), cmd)
            ups3 = [c for c in settings_commands(settings, "UserPromptSubmit")
                    if "qmd-recall-hook.py" in c]
            check(len(ups3) == 1,
                  "a collection change leaves one recall entry, not two (found %d)" % len(ups3))

        # the hook actually fires
        if kitlib.find_qmd(env):
            payload = json.dumps({
                "prompt": "what did we decide about migrations that add a non-null column "
                          "to a big table",
                "session_id": "selftest-1"})
            hr = subprocess.run([sys.executable, str(recall), "--collection", collection],
                                input=payload, capture_output=True, text=True, env=env,
                                timeout=60)
            out = hr.stdout or ""
            ok = '"additionalContext"' in out
            check(ok, "recall hook returns additionalContext for a matching prompt",
                  out + hr.stderr)
            check("migrations-need-a-backfill-plan" in out,
                  "additionalContext points at the example memo path", out)

            # dedupe: the same session must not get the same path twice
            hr2 = subprocess.run([sys.executable, str(recall), "--collection", collection],
                                 input=payload, capture_output=True, text=True, env=env,
                                 timeout=60)
            check((hr2.stdout or "").strip() == "",
                  "per-session dedupe suppresses a repeat of the same hit", hr2.stdout)

            # a vague prompt must stay silent
            vague = json.dumps({"prompt": "hello there how is everything going today ok",
                                "session_id": "selftest-2"})
            hr3 = subprocess.run([sys.executable, str(recall), "--collection", collection],
                                 input=vague, capture_output=True, text=True, env=env,
                                 timeout=60)
            check((hr3.stdout or "").strip() == "", "vague prompt prints nothing", hr3.stdout)

            # --prompt path, the documented by-hand verification
            hr4 = subprocess.run(
                [sys.executable, str(recall), "--collection", collection, "--prompt",
                 "what did we decide about migrations that add a non-null column"],
                capture_output=True, text=True, env=env, timeout=60)
            check('"additionalContext"' in (hr4.stdout or ""),
                  "--prompt verification path works", hr4.stdout + hr4.stderr)

            # S1-3: the documented verify command must be REPEATABLE. `--prompt` alone
            # hashes a fixed session id to one never-rotated state file, so a second run
            # is silent; `--no-dedupe` is what the installer and README now print.
            verify = [sys.executable, str(recall), "--collection", collection,
                      "--no-dedupe", "--prompt",
                      "what did we decide about migrations that add a non-null column"]
            v1 = subprocess.run(verify, capture_output=True, text=True, env=env, timeout=60)
            v2 = subprocess.run(verify, capture_output=True, text=True, env=env, timeout=60)
            v3 = subprocess.run(verify, capture_output=True, text=True, env=env, timeout=60)
            check('"additionalContext"' in (v1.stdout or ""),
                  "--no-dedupe verify prints on run 1", v1.stdout + v1.stderr)
            check('"additionalContext"' in (v2.stdout or ""),
                  "--no-dedupe verify prints again on run 2 (S1-3)", v2.stdout + v2.stderr)
            check('"additionalContext"' in (v3.stdout or ""),
                  "--no-dedupe verify prints again on run 3 (S1-3)", v3.stdout + v3.stderr)
            check((v1.stdout or "") == (v2.stdout or "") == (v3.stdout or ""),
                  "--no-dedupe verify is byte-identical across runs")
            # and the in-session dedupe it bypasses is still in force without the flag
            again = subprocess.run(
                [sys.executable, str(recall), "--collection", collection, "--prompt",
                 "what did we decide about migrations that add a non-null column"],
                capture_output=True, text=True, env=env, timeout=60)
            check((again.stdout or "").strip() == "",
                  "without --no-dedupe the repeat is still suppressed", again.stdout)

            # S2-12: the installed hook must carry an absolute qmd path and must fire
            # with a PATH that has no qmd on it (nvm / custom npm prefix / launchd).
            qmd_path = kitlib.find_qmd(env)
            check("--qmd" in cmd and qmd_path in cmd,
                  "hook command bakes in the absolute qmd path", cmd)
            bare = dict(env)
            bare["PATH"] = "/usr/bin:/bin"
            check(kitlib.find_qmd(bare) is None,
                  "test precondition: qmd is not on the stripped PATH")
            hb = subprocess.run(
                [sys.executable, str(recall), "--collection", collection, "--qmd", qmd_path,
                 "--no-dedupe", "--prompt",
                 "what did we decide about migrations that add a non-null column"],
                capture_output=True, text=True, env=bare, timeout=60)
            check('"additionalContext"' in (hb.stdout or ""),
                  "hook still fires with a stripped PATH thanks to the baked-in qmd (S2-12)",
                  hb.stdout + hb.stderr)
            # a bad baked-in path must say so on stderr and fall back, not fail silently
            hn = subprocess.run(
                [sys.executable, str(recall), "--collection", collection,
                 "--qmd", str(root / "no-such-qmd"), "--no-dedupe", "--prompt",
                 "what did we decide about migrations that add a non-null column"],
                capture_output=True, text=True, env=env, timeout=60)
            check("not executable" in (hn.stderr or "") and hn.returncode == 0,
                  "an unusable baked-in qmd path is reported on stderr (S2-12)",
                  "rc=%s err=%r" % (hn.returncode, hn.stderr))
            check('"additionalContext"' in (hn.stdout or ""),
                  "...and the PATH fallback still finds qmd", hn.stdout)

            # refresh script: baked qmd path, and it must not claim a scope it lacks
            rtext = refresh.read_text(encoding="utf-8")
            check(qmd_path in rtext and "@@QMD@@" not in rtext,
                  "refresh-brain.py has the qmd path baked in")

            rr = subprocess.run([sys.executable, str(refresh)], capture_output=True,
                                text=True, env=env, timeout=1800)
            check(rr.returncode == 0 and (rr.stdout or "").startswith("OK "),
                  "refresh-brain.py runs cleanly", rr.stdout + rr.stderr)
            check("scope=" in (rr.stdout or ""),
                  "refresh-brain.py states the index scope it actually used", rr.stdout)
            rb = subprocess.run([sys.executable, str(refresh)], capture_output=True,
                                text=True, env=bare, timeout=1800)
            check(rb.returncode == 0 and (rb.stdout or "").startswith("OK "),
                  "refresh-brain.py runs with a stripped PATH too", rb.stdout + rb.stderr)
        else:
            skip("qmd not on PATH — hook and refresh not exercised")

        # handoff hook writes a stub
        hopayload = json.dumps({"session_id": "selftestsession", "cwd": str(root / "demo-proj"),
                                "reason": "other"})
        subprocess.run([sys.executable, str(handoff), "--brain-dir", str(brain_dir)],
                       input=hopayload, capture_output=True, text=True, env=env, timeout=60)
        stubs = sorted((brain_dir / "memory" / "handoffs").glob("*.md")) \
            if (brain_dir / "memory" / "handoffs").is_dir() else []
        check(len(stubs) == 1, "handoff hook wrote one stub (found %d)" % len(stubs))
        if stubs:
            text = stubs[0].read_text(encoding="utf-8")
            check(text.startswith("---") and "type: project" in text,
                  "handoff stub has valid frontmatter")
            check("demo-proj" in text, "handoff stub names the project")

        # S2-12(b): the uninstaller must name the collection that was actually installed,
        # not the literal default "brain".
        sys.path.insert(0, str(KIT))
        import uninstall as uninstall_mod  # noqa: E402
        found = uninstall_mod.installed_collection(settings)
        check(found == collection,
              "uninstall reads the installed collection out of settings.json (got %r)" % found)

        # SEV3 nit 6: settings.json backups are pruned, not accumulated forever.
        for _ in range(9):
            subprocess.run([sys.executable, str(KIT / "merge_settings.py"), str(settings),
                            "UserPromptSubmit", "echo baktest"],
                           capture_output=True, text=True, env=env, timeout=60)
        baks = sorted(claude_dir.glob("settings.json.bak.*"))
        check(len(baks) <= 5, "settings.json backups are pruned (found %d)" % len(baks))
        subprocess.run([sys.executable, str(KIT / "merge_settings.py"), str(settings),
                        "UserPromptSubmit", "echo baktest", "--remove"],
                       capture_output=True, text=True, env=env, timeout=60)

        # uninstall
        ur = subprocess.run([sys.executable, str(KIT / "uninstall.py"),
                             "--claude-dir", str(claude_dir), "--brain-dir", str(brain_dir),
                             "--collection", collection],
                            capture_output=True, text=True, env=env, timeout=300)
        check(ur.returncode == 0, "uninstall.py completed", ur.stdout + ur.stderr)
        check(not any("qmd-recall-hook.py" in c
                      for c in settings_commands(settings, "UserPromptSubmit")),
              "UserPromptSubmit entry removed")
        check(not any("session-handoff-hook.py" in c
                      for c in settings_commands(settings, "SessionEnd")),
              "SessionEnd entry removed")
        for p, label in ((recall, "recall hook removed"), (handoff, "handoff hook removed"),
                         (refresh, "refresh-brain.py removed"),
                         (claude_dir / "skills" / "brain-search" / "SKILL.md",
                          "brain-search skill removed"),
                         (claude_dir / "commands" / "remember.md", "/remember removed")):
            check(not p.exists(), label)
        check((brain_dir / "README.md").is_file() and (brain_dir / "memory").is_dir(),
              "notes folder left alone by uninstall")
    finally:
        qmd = kitlib.find_qmd(env)
        if qmd:
            subprocess.run([qmd, "collection", "remove", collection],
                           capture_output=True, text=True, env=env, timeout=300)
        if keep:
            print("\n-- kept: %s" % root)
        else:
            shutil.rmtree(root, ignore_errors=True)


# ------------------------------------------------- part 2: Windows branches, logic only
def windows_unit_tests():
    print("\n== Windows branches (logic-tested on this platform, not run on Windows)\n")

    win_env = {"USERPROFILE": r"C:\Users\Sam", "PATH": r"C:\Windows\System32"}
    check(kitlib.claude_config_dir(win_env, windows=True) == Path(r"C:\Users\Sam") / ".claude",
          "config dir resolves under %USERPROFILE% on Windows",
          kitlib.claude_config_dir(win_env, windows=True))
    check(kitlib.default_notes_dir(win_env, windows=True) == Path(r"C:\Users\Sam") / "brain",
          "notes dir defaults under %USERPROFILE% on Windows")

    override = dict(win_env, CLAUDE_CONFIG_DIR=r"D:\claude-config")
    check(kitlib.claude_config_dir(override, windows=True) == Path(r"D:\claude-config"),
          "CLAUDE_CONFIG_DIR overrides the Windows default")

    posix_env = {"HOME": "/home/sam", "PATH": "/usr/bin"}
    check(kitlib.claude_config_dir(posix_env, windows=False) == Path("/home/sam/.claude"),
          "config dir resolves under $HOME on POSIX")
    check(kitlib.claude_config_dir(dict(posix_env, CLAUDE_CONFIG_DIR="/opt/cc"),
                                   windows=False) == Path("/opt/cc"),
          "CLAUDE_CONFIG_DIR overrides the POSIX default")

    # With os.name patched, pathlib refuses to build a WindowsPath on a POSIX host, so the
    # auto-detection is checked through the string-only command builder instead.
    with mock.patch.object(os, "name", "nt"), mock.patch.object(sys, "platform", "win32"):
        check(kitlib.is_windows() is True, "is_windows() follows a monkeypatched os.name")
        auto = kitlib.hook_command(r"C:\hooks\h.py", ["--collection", "my brain"],
                                   python=r"C:\Program Files\Python\python.exe")
        check(auto.startswith('"C:\\Program Files') and '"my brain"' in auto,
              "command builder auto-selects Windows quoting from os.name", auto)
    with mock.patch.object(os, "name", "posix"), mock.patch.object(sys, "platform", "linux"):
        check(kitlib.is_windows() is False, "is_windows() is False on a posix os.name")

    # command quoting
    win_cmd = kitlib.hook_command(r"C:\Users\Sam\.claude\hooks\qmd-recall-hook.py",
                                  ["--collection", "brain"],
                                  python=r"C:\Program Files\Python39\python.exe",
                                  windows=True)
    check(win_cmd.startswith('"C:\\Program Files\\Python39\\python.exe"'),
          "Windows: an interpreter path with a space is double-quoted", win_cmd)
    check('"C:\\Users\\Sam\\.claude\\hooks\\qmd-recall-hook.py"' in win_cmd or
          "C:\\Users\\Sam\\.claude\\hooks\\qmd-recall-hook.py" in win_cmd,
          "Windows: the hook path is present and unmangled", win_cmd)
    check(win_cmd.endswith("--collection brain"),
          "Windows: a space-free argument is left unquoted", win_cmd)
    check("'" not in win_cmd, "Windows: no POSIX single quotes leak into the command", win_cmd)

    spacey = kitlib.hook_command(r"C:\My Hooks\qmd-recall-hook.py",
                                 ["--collection", "my brain"],
                                 python=r"C:\Python\python.exe", windows=True)
    check('"C:\\My Hooks\\qmd-recall-hook.py"' in spacey,
          "Windows: a hook path with a space is double-quoted", spacey)
    check('"my brain"' in spacey,
          "Windows: an argument with a space is double-quoted", spacey)

    posix_cmd = kitlib.hook_command("/home/sam/.claude/hooks/qmd-recall-hook.py",
                                    ["--collection", "my brain"],
                                    python="/usr/bin/python3", windows=False)
    check(posix_cmd.startswith("/usr/bin/python3 "), "POSIX: plain paths stay unquoted",
          posix_cmd)
    check("'my brain'" in posix_cmd, "POSIX: an argument with a space is shell-quoted",
          posix_cmd)

    # qmd.cmd lookup
    tmp = Path(tempfile.mkdtemp(prefix="kit-which-"))
    try:
        (tmp / "qmd.cmd").write_text("@echo off\r\n", encoding="utf-8")
        # Real Windows needs no executable bit; this host's shutil.which does, so the
        # fixture carries one and the check stays about the .cmd name, not the mode.
        os.chmod(tmp / "qmd.cmd", 0o755)
        found = kitlib.find_qmd({"PATH": str(tmp)}, windows=True)
        check(found is not None and Path(found).name == "qmd.cmd",
              "Windows: find_qmd() picks up qmd.cmd", found)
        check(kitlib.find_qmd({"PATH": str(tmp)}, windows=False) is None,
              "POSIX: a bare qmd.cmd is not mistaken for qmd")
        npm = tmp / "npm.cmd"
        npm.write_text("@echo off\r\n", encoding="utf-8")
        os.chmod(npm, 0o755)
        check(kitlib.find_npm({"PATH": str(tmp)}, windows=True) is not None,
              "Windows: find_npm() picks up npm.cmd")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    check("npm i -g qmd" in kitlib.npm_install_hint(windows=True) and
          "install.bat" in kitlib.npm_install_hint(windows=True),
          "Windows: the missing-qmd message names npm and install.bat")
    check("install.sh" in kitlib.npm_install_hint(windows=False),
          "POSIX: the missing-qmd message names install.sh")

    # the recall hook's own temp-file and qmd lookup logic
    sys.path.insert(0, str(KIT / "hooks"))
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "recall_hook", str(KIT / "hooks" / "qmd-recall-hook.py"))
    hook = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hook)
    state = hook.state_path("abc/def:ghi")
    check(state.parent == Path(tempfile.gettempdir()),
          "recall hook: dedupe file lands in the platform temp dir", state)
    check(all(c not in state.name for c in '\\/:*?"<>|'),
          "recall hook: dedupe filename is legal on Windows", state.name)
    check("qmd.cmd" in hook.QMD_NAMES, "recall hook: qmd lookup includes qmd.cmd")
    opts = hook.parse_argv(["--collection", "notes", "--max-hits", "2", "--min-score", "70"])
    check(opts["collection"] == "notes" and opts["max_hits"] == 2 and opts["min_score"] == 70,
          "recall hook: command-line options parse", opts)
    o2 = hook.parse_argv(["--no-dedupe", "--qmd", "/opt/x/bin/qmd"])
    check(o2["no_dedupe"] is True and o2["qmd"] == "/opt/x/bin/qmd",
          "recall hook: --no-dedupe and --qmd parse", o2)
    check(hook.parse_argv(["--fresh-session"])["no_dedupe"] is True,
          "recall hook: --fresh-session is accepted as an alias")
    check(hook.find_qmd("/definitely/not/here/qmd") != "/definitely/not/here/qmd",
          "recall hook: an unusable baked-in path falls back rather than being trusted")

    # S2-12: with no qmd anywhere, the hook must SAY so rather than exit silently.
    import io
    with mock.patch.object(hook, "find_qmd", return_value=None), \
            mock.patch.object(sys, "stderr", io.StringIO()) as err:
        rc = hook.main(["--prompt",
                        "what did we decide about migrations that add a non-null column"])
    msg = err.getvalue()
    check(rc == 0 and "qmd not found" in msg and "recall is OFF" in msg,
          "recall hook: a missing qmd writes a diagnostic to stderr (S2-12)",
          "rc=%s msg=%r" % (rc, msg))

    # SEV3 nit 6: refresh only claims a per-collection scope when qmd offers one.
    rspec = importlib.util.spec_from_file_location("kit_refresh", str(KIT / "refresh.py"))
    refresh_mod = importlib.util.module_from_spec(rspec)
    rspec.loader.exec_module(refresh_mod)
    with mock.patch.object(refresh_mod.subprocess, "run",
                           return_value=mock.Mock(stdout="  qmd update [--pull]  - Re-index\n")):
        check(refresh_mod.update_supports_collection("/bin/qmd") is False,
              "refresh: no collection flag claimed when qmd update does not offer one")
    with mock.patch.object(refresh_mod.subprocess, "run",
                           return_value=mock.Mock(
                               stdout="  qmd update [-c <name>]  - Re-index one collection\n")):
        check(refresh_mod.update_supports_collection("/bin/qmd") is True,
              "refresh: the collection flag is used when qmd update does offer one")
    check(hook.parse_argv(["--collection"])["collection"] is not None,
          "recall hook: a truncated argument does not crash it")


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--keep", action="store_true", help="keep the throwaway home directory")
    args = p.parse_args(argv)

    end_to_end(keep=args.keep)
    windows_unit_tests()

    total = len(CHECKS)
    failed = total - sum(CHECKS)
    print("\n== %d/%d checks passed" % (total - failed, total))
    if failed:
        print("== %d check(s) FAILED" % failed)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
