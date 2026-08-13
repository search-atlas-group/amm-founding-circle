#!/usr/bin/env python3
"""
structural-diff.py - compare the structure & content of two web pages.

Free, single-page migration QA: fetches an OLD page and its NEW (rebuilt)
version and compares title, meta description, canonical, heading outline,
link count, image count, and word count. Reads HTML only (no browser), so
JS-rendered content may be under-counted - trust screenshots for appearance.

Each argument may be a URL or a path to a saved HTML file.

Usage:
    python3 structural-diff.py "https://old.example.com/p/" "https://new.example.com/p/"
    python3 structural-diff.py old.html new.html
"""
import sys
import re
import os
import argparse
import urllib.request
from html.parser import HTMLParser
from html import unescape


def load(arg):
    if os.path.isfile(arg):
        return open(arg, encoding="utf-8", errors="replace").read()
    scheme = arg.split("://", 1)[0].lower() if "://" in arg else ""
    if scheme not in ("http", "https"):
        raise ValueError(f"Refusing to fetch non-http(s) URL: {arg!r}")
    req = urllib.request.Request(
        arg, headers={"User-Agent": "Mozilla/5.0 (website-migration-starter)"}
    )
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read().decode("utf-8", "replace")


class Extract(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = ""
        self.meta_desc = ""
        self.canonical = ""
        self.headings = []          # (level, text)
        self.links = 0
        self.images = 0
        self._cur = None            # current heading level being captured
        self._buf = []
        self._skip = 0              # inside script/style
        self._text = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("script", "style"):
            self._skip += 1
        elif tag == "title":
            self._cur = "title"
            self._buf = []
        elif tag == "meta":
            name = (a.get("name") or a.get("property") or "").lower()
            if name in ("description", "og:description") and not self.meta_desc:
                self.meta_desc = (a.get("content") or "").strip()
        elif tag == "link" and (a.get("rel") or "").lower() == "canonical":
            self.canonical = (a.get("href") or "").strip()
        elif tag in ("h1", "h2", "h3"):
            self._cur = tag
            self._buf = []
        elif tag == "a" and a.get("href"):
            self.links += 1
        elif tag == "img":
            self.images += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._skip:
            self._skip -= 1
        elif tag == "title" and self._cur == "title":
            self.title = unescape("".join(self._buf)).strip()
            self._cur = None
        elif tag in ("h1", "h2", "h3") and self._cur == tag:
            txt = unescape("".join(self._buf)).strip()
            if txt:
                self.headings.append((int(tag[1]), txt))
            self._cur = None

    def handle_data(self, data):
        if self._cur:
            self._buf.append(data)
        if not self._skip:
            self._text.append(data)

    def word_count(self):
        words = re.findall(r"\w+", unescape(" ".join(self._text)))
        return len(words)


def analyze(html):
    e = Extract()
    try:
        e.feed(html)
    except Exception:
        pass
    return {
        "title": e.title,
        "meta_desc": e.meta_desc,
        "canonical": e.canonical,
        "headings": e.headings,
        "h_count": len(e.headings),
        "links": e.links,
        "images": e.images,
        "words": e.word_count(),
    }


def line(label, old, new):
    flag = "" if old == new else "  <-- DIFFERS"
    return f"{label:<16} | {str(old)[:40]:<40} | {str(new)[:40]:<40}{flag}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("old", help="original page URL or saved HTML file")
    ap.add_argument("new", help="rebuilt page URL or saved HTML file")
    args = ap.parse_args()

    try:
        o = analyze(load(args.old))
        n = analyze(load(args.new))
    except Exception as ex:
        print(f"Could not load a page ({ex}). If the site can't be reached, "
              "save each page's HTML to a file and pass the file paths instead.",
              file=sys.stderr)
        sys.exit(1)

    print(f"{'FIELD':<16} | {'OLD (original)':<40} | {'NEW (rebuilt)':<40}")
    print("-" * 100)
    print(line("Title", o["title"], n["title"]))
    print(line("Meta description", o["meta_desc"] or "(none)", n["meta_desc"] or "(none)"))
    print(line("Canonical", o["canonical"] or "(none)", n["canonical"] or "(none)"))
    print(line("Headings (#)", o["h_count"], n["h_count"]))
    print(line("Links (#)", o["links"], n["links"]))
    print(line("Images (#)", o["images"], n["images"]))
    print(line("Word count", o["words"], n["words"]))

    # Headings that exist on old but are missing on new (the dangerous case)
    old_h = {t.lower() for _, t in o["headings"]}
    new_h = {t.lower() for _, t in n["headings"]}
    missing = [t for lvl, t in o["headings"] if t.lower() not in new_h]
    added = [t for lvl, t in n["headings"] if t.lower() not in old_h]

    print("\nSUMMARY")
    issues = []
    if not n["meta_desc"] and o["meta_desc"]:
        issues.append("- New page is MISSING its meta description.")
    if o["canonical"] and n["canonical"] and o["canonical"] != n["canonical"]:
        issues.append("- Canonical tag changed (expected if the domain changed).")
    if missing:
        issues.append(f"- {len(missing)} heading(s) on the old page are MISSING on the new one:")
        issues += [f"    * {t}" for t in missing[:10]]
    if n["images"] < o["images"]:
        issues.append(f"- New page has FEWER images ({n['images']} vs {o['images']}).")
    if o["words"] and n["words"] < o["words"] * 0.8:
        issues.append(f"- New page has notably less text ({n['words']} vs {o['words']} words).")
    if added:
        issues.append(f"- {len(added)} new heading(s) not on the old page (often fine).")

    if issues:
        print("\n".join(issues))
    else:
        print("- Structure and content look like a close match. "
              "Confirm appearance with screenshots.")
    print("\nNote: this reads raw HTML. If the new site renders with JavaScript, "
          "some content may be under-counted - verify appearance with screenshots.")


if __name__ == "__main__":
    main()
