#!/usr/bin/env python3
"""Merge kit hook entries into a Claude Code settings.json without clobbering existing hooks.

Usage: merge_settings.py <settings.json> <event> <command> [--timeout N] [--remove]
                         [--match SUBSTRING]

Idempotent: an entry whose command string matches is replaced, not duplicated. With
--match, any entry whose command contains that substring is replaced too, so re-installing
with a different collection, notes folder or interpreter updates the entry in place instead
of leaving a stale second copy behind. Every other
hook in the file is preserved byte-for-byte in content. Writes a timestamped .bak first and
validates the result parses as JSON before replacing the original. Only the newest
KEEP_BACKUPS backups are kept, so re-running the installer cannot litter the config dir.
"""
import sys, json, os, shutil, datetime, glob

KEEP_BACKUPS = 5


def prune_backups(path, keep=KEEP_BACKUPS):
    """Keep only the newest `keep` timestamped backups of `path`."""
    baks = sorted(glob.glob(path + ".bak.*"))
    for old in baks[:-keep] if keep >= 0 else []:
        try:
            os.remove(old)
        except OSError:
            pass
    return baks[:-keep] if keep >= 0 else []

def load(path):
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return {}
    with open(path) as f:
        return json.load(f)

def main():
    args = sys.argv[1:]
    remove = "--remove" in args
    if remove: args.remove("--remove")
    match = None
    if "--match" in args:
        i = args.index("--match"); match = args[i+1]; del args[i:i+2]
    timeout = 5
    if "--timeout" in args:
        i = args.index("--timeout"); timeout = int(args[i+1]); del args[i:i+2]
    if len(args) < 3:
        print("usage: merge_settings.py <settings.json> <event> <command> "
              "[--timeout N] [--remove] [--match SUBSTRING]", file=sys.stderr)
        return 2
    path, event, command = args[0], args[1], args[2]

    try:
        data = load(path)
    except json.JSONDecodeError as e:
        print("ERROR: %s is not valid JSON (%s). Fix it before installing." % (path, e), file=sys.stderr)
        return 1
    if not isinstance(data, dict):
        print("ERROR: %s does not contain a JSON object." % path, file=sys.stderr)
        return 1

    hooks = data.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        print("ERROR: 'hooks' in %s is not an object." % path, file=sys.stderr)
        return 1
    matchers = hooks.setdefault(event, [])
    if not isinstance(matchers, list):
        print("ERROR: hooks.%s in %s is not a list." % (event, path), file=sys.stderr)
        return 1

    entry = {"type": "command", "command": command, "timeout": timeout}

    # Strip any existing entry with the same command, anywhere under this event.
    changed = False
    for m in matchers:
        inner = m.get("hooks") if isinstance(m, dict) else None
        if not isinstance(inner, list): continue
        before = len(inner)
        m["hooks"] = [h for h in inner
                      if not (isinstance(h, dict)
                              and (h.get("command") == command
                                   or (match and match in str(h.get("command", "")))))]
        if len(m["hooks"]) != before: changed = True
    matchers[:] = [m for m in matchers
                   if not (isinstance(m, dict) and m.get("hooks") == [] and set(m) <= {"hooks", "matcher"})]

    if not remove:
        matchers.append({"hooks": [entry]})
        changed = True
    if not matchers:
        hooks.pop(event, None)
    if not hooks:
        data.pop("hooks", None)

    text = json.dumps(data, indent=2) + "\n"
    json.loads(text)  # validate before we touch the original

    if os.path.exists(path):
        bak = "%s.bak.%s" % (path, datetime.datetime.now().strftime("%Y%m%d-%H%M%S"))
        shutil.copy2(path, bak)
        print("backup: %s" % bak)
        pruned = prune_backups(path)
        if pruned:
            print("pruned %d old backup(s), keeping the newest %d" % (len(pruned), KEEP_BACKUPS))
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f: f.write(text)
    os.replace(tmp, path)
    print(("removed" if remove else "merged") + " %s hook -> %s" % (event, path))
    return 0

if __name__ == "__main__":
    sys.exit(main())
