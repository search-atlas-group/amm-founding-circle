#!/usr/bin/env python3
"""
extract-wp-post.py - pull ONE WordPress page/post into clean Markdown + image list.

This is the free, single-page version of a content migration. It fetches a post
or page from a standard WordPress site's public REST API and converts the body
to Markdown. No login, no plugin, no admin access required.

Usage:
    python3 extract-wp-post.py "https://example.com/some-post/"
    python3 extract-wp-post.py some-post-slug --site https://example.com
    python3 extract-wp-post.py --html saved-page.html      # convert pasted HTML
    python3 extract-wp-post.py --json saved-wp-item.json   # convert a saved WP REST item

Deliberately one page at a time. Whole-site extraction (with image localization,
internal-link rewriting, and SEO preservation) is a separate, automated job.
"""
import sys
import json
import re
import argparse
import urllib.request
import urllib.parse
from html import unescape


def fetch(url):
    scheme = url.split("://", 1)[0].lower() if "://" in url else ""
    if scheme not in ("http", "https"):
        raise ValueError(f"Refusing to fetch non-http(s) URL: {url!r}")
    req = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0 (website-migration-starter)"}
    )
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read().decode("utf-8", "replace")


def html_to_markdown(html):
    """Convert HTML to Markdown. Prefers markdownify; falls back to a simple
    built-in converter so the tool still works with zero installed packages."""
    try:
        from markdownify import markdownify as md  # type: ignore
        return md(html, heading_style="ATX", bullets="-").strip()
    except Exception:
        pass

    # --- Minimal stdlib fallback (good enough for a single-page taste) ---
    text = html
    text = re.sub(r"(?is)<(script|style).*?</\1>", "", text)
    for n in range(1, 7):
        text = re.sub(rf"(?is)<h{n}[^>]*>(.*?)</h{n}>",
                      lambda m, n=n: "\n" + "#" * n + " " + strip_tags(m.group(1)) + "\n", text)
    text = re.sub(r'(?is)<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>',
                  lambda m: f"[{strip_tags(m.group(2))}]({m.group(1)})", text)
    text = re.sub(r'(?is)<img[^>]*src="([^"]*)"[^>]*?(?:alt="([^"]*)")?[^>]*>',
                  lambda m: f"![{m.group(2) or ''}]({m.group(1)})", text)
    text = re.sub(r"(?is)</(p|div|section|li|tr|h[1-6])>", "\n", text)
    text = re.sub(r"(?is)<li[^>]*>", "- ", text)
    text = re.sub(r"(?is)<br[^>]*>", "\n", text)
    text = strip_tags(text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def strip_tags(s):
    return unescape(re.sub(r"(?is)<[^>]+>", "", s)).strip()


def image_urls(html):
    urls = re.findall(r'(?is)<img[^>]*\ssrc="([^"]+)"', html)
    seen, out = set(), []
    for u in urls:
        if u in seen:
            continue
        seen.add(u)
        if not re.search(r"(spacer|pixel|1x1)\.gif$", u, re.I):
            out.append(u)
    return out


def derive(url_or_slug, site):
    if url_or_slug.startswith("http"):
        p = urllib.parse.urlparse(url_or_slug)
        site = f"{p.scheme}://{p.netloc}"
        parts = [s for s in p.path.split("/") if s]
        slug = parts[-1] if parts else ""
    else:
        slug = url_or_slug.strip("/")
    return site, slug


def get_item(site, slug):
    for kind in ("posts", "pages"):
        api = f"{site}/wp-json/wp/v2/{kind}?slug={urllib.parse.quote(slug)}&_embed=1"
        try:
            data = json.loads(fetch(api))
        except Exception:
            continue
        if isinstance(data, list) and data:
            return data[0]
    return None


def render_item(item):
    title = unescape(strip_tags(item.get("title", {}).get("rendered", "Untitled")))
    date = (item.get("date") or "")[:10]
    body_html = item.get("content", {}).get("rendered", "")
    excerpt = strip_tags(item.get("excerpt", {}).get("rendered", ""))
    author = ""
    try:
        author = item["_embedded"]["author"][0]["name"]
    except Exception:
        pass

    out = ["---", f"title: {title}"]
    if date:
        out.append(f"date: {date}")
    if author:
        out.append(f"author: {author}")
    if excerpt:
        out.append(f"excerpt: {excerpt}")
    out += ["---", "", html_to_markdown(body_html), ""]

    imgs = image_urls(body_html)
    out.append(f"## Images ({len(imgs)})")
    out += [f"- {u}" for u in imgs] or ["- (none found)"]
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("target", nargs="?", help="WordPress post/page URL or slug")
    ap.add_argument("--site", default="", help="Site base URL (when target is a slug)")
    ap.add_argument("--html", help="Convert a saved HTML file instead of fetching")
    ap.add_argument("--json", help="Convert a saved WP REST item JSON instead of fetching")
    args = ap.parse_args()

    if args.html:
        html = open(args.html, encoding="utf-8", errors="replace").read()
        print("---\ntitle: (from pasted HTML)\n---\n")
        print(html_to_markdown(html))
        imgs = image_urls(html)
        print(f"\n## Images ({len(imgs)})")
        print("\n".join(f"- {u}" for u in imgs) or "- (none found)")
        return

    if args.json:
        item = json.load(open(args.json, encoding="utf-8"))
        print(render_item(item))
        return

    if not args.target:
        ap.error("give a WordPress URL or slug (or use --html / --json)")

    site, slug = derive(args.target, args.site)
    if not site:
        ap.error("could not determine the site - pass a full URL or use --site")
    item = get_item(site, slug)
    if not item:
        print(f"Could not find '{slug}' via {site}/wp-json/wp/v2/. "
              "Is it a WordPress site, and is the REST API public? "
              "If the site can't be reached, paste the page HTML and use --html.",
              file=sys.stderr)
        sys.exit(1)
    print(render_item(item))


if __name__ == "__main__":
    main()
