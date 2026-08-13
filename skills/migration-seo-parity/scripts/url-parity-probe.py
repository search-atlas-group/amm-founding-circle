#!/usr/bin/env python3
"""
url-parity-probe.py - check the SEO signals that break rankings at migration.

Free, single-URL migration check. For one URL (or an old/new pair) it reports:
final HTTP status, redirect chain, canonical tag, indexability (meta robots /
X-Robots-Tag), and trailing-slash form. In compare mode it flags mismatches.

Usage:
    python3 url-parity-probe.py "https://example.com/page/"
    python3 url-parity-probe.py "https://old.example.com/p/" "https://new.example.com/p/"

Whole-site redirect-map generation and parity reconciliation is a separate,
automated job - this checks one URL at a time.
"""
import sys
import re
import argparse
import urllib.request
import urllib.error
from html import unescape


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """Capture redirects instead of following them silently."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise _Redirect(code, newurl)


class _Redirect(Exception):
    def __init__(self, code, location):
        self.code = code
        self.location = location


def request_once(url):
    scheme = url.split("://", 1)[0].lower() if "://" in url else ""
    if scheme not in ("http", "https"):
        raise ValueError(f"Refusing to fetch non-http(s) URL: {url!r}")
    opener = urllib.request.build_opener(NoRedirect)
    req = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0 (website-migration-starter)"}
    )
    try:
        with opener.open(req, timeout=25) as r:
            body = r.read().decode("utf-8", "replace")
            return r.status, dict(r.headers), body, None
    except _Redirect as rd:
        return rd.code, {}, "", rd.location
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers or {}), "", None


def probe(url, max_hops=10):
    chain = []
    cur = url
    status, headers, body = None, {}, ""
    for _ in range(max_hops):
        status, headers, body, location = request_once(cur)
        if location:
            chain.append((status, cur, location))
            # resolve relative redirects
            if location.startswith("/"):
                m = re.match(r"(https?://[^/]+)", cur)
                location = (m.group(1) if m else "") + location
            cur = location
            continue
        break

    canonical = ""
    m = re.search(r'(?is)<link[^>]+rel=["\']canonical["\'][^>]*href=["\']([^"\']+)', body)
    if m:
        canonical = m.group(1).strip()

    noindex = False
    mr = re.search(r'(?is)<meta[^>]+name=["\']robots["\'][^>]*content=["\']([^"\']+)', body)
    robots_meta = mr.group(1).lower() if mr else ""
    xrobots = (headers.get("X-Robots-Tag") or "").lower()
    if "noindex" in robots_meta or "noindex" in xrobots:
        noindex = True

    final = cur
    slash = "trailing slash" if final.rstrip("?").endswith("/") else "no trailing slash"

    return {
        "input": url,
        "final": final,
        "status": status,
        "chain": chain,
        "canonical": canonical,
        "indexable": not noindex,
        "robots": robots_meta or xrobots or "(default: indexable)",
        "slash": slash,
    }


def report(p):
    print(f"URL:          {p['input']}")
    if p["chain"]:
        print("Redirects:")
        for code, frm, to in p["chain"]:
            print(f"   {code}  {frm}  ->  {to}")
        print(f"Final URL:    {p['final']}")
    print(f"Final status: {p['status']}")
    print(f"Indexable:    {'YES' if p['indexable'] else 'NO  <-- will be hidden from Google'}  ({p['robots']})")
    print(f"Canonical:    {p['canonical'] or '(none set)'}")
    print(f"Slash form:   {p['slash']}")

    warns = []
    if p["status"] and p["status"] >= 400:
        warns.append(f"Page returns {p['status']} - broken; fix before launch.")
    if not p["indexable"]:
        warns.append("Page is set to NOINDEX - it will not appear in Google.")
    if p["chain"] and p["status"] and p["status"] >= 400:
        warns.append("Redirect lands on an error - the redirect target is wrong.")
    if len(p["chain"]) > 1:
        warns.append(f"Redirect CHAIN ({len(p['chain'])} hops) - collapse to a single 301.")
    if warns:
        print("WARNINGS:")
        for w in warns:
            print(f"   ! {w}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url", help="URL to probe (the new page, or the old one)")
    ap.add_argument("new", nargs="?", help="optional: the new URL, to compare against the old")
    args = ap.parse_args()

    try:
        if args.new:
            old = probe(args.url)
            new = probe(args.new)
            print("=== OLD (original) ===")
            report(old)
            print("\n=== NEW (rebuilt) ===")
            report(new)
            print("\n=== COMPARISON ===")
            if old["indexable"] and not new["indexable"]:
                print(" ! New page is noindex but the old one was indexable - RANKING LOSS RISK.")
            if old["slash"] != new["slash"]:
                print(f" ! Trailing-slash convention changed ({old['slash']} -> {new['slash']}).")
            if new["canonical"] and new["final"].rstrip("/") not in new["canonical"].rstrip("/"):
                print(" ! New page's canonical does not point to itself - check it.")
            if not (old["indexable"] and not new["indexable"]) and old["slash"] == new["slash"]:
                print(" Looks consistent. Walk through the full cutover checklist next.")
        else:
            report(probe(args.url))
            print("\nNext: review references/cutover-checklist.md before launch.")
    except Exception as ex:
        print(f"Could not reach the URL ({ex}). Check the address, or that this "
              "environment has internet access.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
