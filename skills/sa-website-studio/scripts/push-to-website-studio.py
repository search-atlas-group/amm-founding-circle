#!/usr/bin/env python3
"""
push-to-website-studio.py - create a SearchAtlas Website Studio project from a domain.

Free, single-project step of a migration. Calls the SearchAtlas MCP API
(website_studio_tools -> create_project) to register a site so SA's AI can rebuild it.

Endpoint : POST https://mcp.searchatlas.com/api/v1/mcp   (JSON-RPC 2.0, tools/call)
Auth     : X-API-KEY header   (get the key from SA dashboard -> Settings -> API Keys)
Tool/op  : website_studio_tools / create_project
Params   : name (req), mode (free|clone|clone_seo|clone_ppc), source_url (clone modes),
           user_prompt (free mode), campaign_id (clone_ppc)

The API key is read from the SA_MCP_API_KEY env var (preferred) or --key.
It is NEVER printed. Creating a project is asynchronous (~5-13 min).

Usage:
    export SA_MCP_API_KEY="..."
    python3 push-to-website-studio.py --url https://example.com --name "Example" --mode clone_seo
    python3 push-to-website-studio.py --url https://example.com --name "Example" --dry-run
    python3 push-to-website-studio.py --list
    python3 push-to-website-studio.py --status <project-id>
    python3 push-to-website-studio.py --credits
    python3 push-to-website-studio.py --discover
"""
import os
import sys
import json
import time
import argparse
import urllib.request
import urllib.error

ENDPOINT = "https://mcp.searchatlas.com/api/v1/mcp"
TOOL = "website_studio_tools"
MAX_RETRIES = 3  # retry-loop-safety: hard cap on transient (429/500) retries; do NOT
                 # wrap this in an outer auto-retry. Bounded backoff, then give up.


def call(api_key, op, params, dry_run=False):
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": TOOL, "arguments": {"op": op, "params": params}},
    }
    if dry_run:
        # Show exactly what would be sent; never reveal the key.
        print(json.dumps(payload, indent=2))
        print("\n[dry-run] POST " + ENDPOINT + "  (header X-API-KEY: ***redacted***)")
        return None

    if not api_key:
        sys.exit("No API key. Set SA_MCP_API_KEY or pass --key. "
                 "Get one from SearchAtlas -> Settings -> API Keys.")

    body = json.dumps(payload).encode("utf-8")
    delay = 1.0
    for attempt in range(1, MAX_RETRIES + 1):
        req = urllib.request.Request(
            ENDPOINT, data=body, method="POST",
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
                "X-API-KEY": api_key,
                "User-Agent": "website-migration-starter",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                raw = r.read().decode("utf-8", "replace")
                return parse_response(raw)
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:400] if e.fp else ""
            if e.code in (429, 500, 502, 503) and attempt < MAX_RETRIES:
                time.sleep(delay)
                delay *= 2
                continue
            sys.exit(f"HTTP {e.code} from SearchAtlas. {http_hint(e.code)}\n{detail}")
        except Exception as ex:
            if attempt < MAX_RETRIES:
                time.sleep(delay)
                delay *= 2
                continue
            sys.exit(f"Request failed: {ex}")
    sys.exit("Gave up after retries.")


def http_hint(code):
    return {
        401: "Authentication failed - the API key is wrong/expired.",
        403: "Forbidden - the key lacks Website Studio scope (check the plan).",
        429: "Rate limited - wait a minute and retry.",
        500: "SearchAtlas backend error (known to hit create_project) - retry; --list/--status still work.",
    }.get(code, "")


def parse_response(raw):
    """Accept plain JSON or an SSE stream (lines like 'data: {...}')."""
    raw = raw.strip()
    obj = None
    if raw.startswith("{"):
        try:
            obj = json.loads(raw)
        except Exception:
            obj = None
    if obj is None:
        # SSE: keep the last data: line that parses as JSON-RPC
        for line in raw.splitlines():
            line = line.strip()
            if line.startswith("data:"):
                chunk = line[5:].strip()
                try:
                    cand = json.loads(chunk)
                    if isinstance(cand, dict):
                        obj = cand
                except Exception:
                    pass
    if obj is None:
        sys.exit("No usable data frame in the response. Try again.")
    return obj


def unwrap(obj):
    """Pull the human-meaningful result out of a JSON-RPC / MCP envelope."""
    if "error" in obj and obj["error"]:
        return None, obj["error"]
    result = obj.get("result", obj)
    # MCP tool results often arrive as {content:[{type:text,text:"..."}], isError}
    if isinstance(result, dict) and "content" in result:
        if result.get("isError"):
            return None, _texts(result)
        parsed = _try_json(_texts(result))
        return (parsed if parsed is not None else _texts(result)), None
    return result, None


def _texts(result):
    out = []
    for c in result.get("content", []):
        if isinstance(c, dict) and c.get("type") == "text":
            out.append(c.get("text", ""))
    return "\n".join(out).strip()


def _try_json(s):
    try:
        return json.loads(s)
    except Exception:
        return None


def summarize_project(data):
    if not isinstance(data, dict):
        return
    pid = data.get("project_id") or data.get("id")
    preview = (data.get("preview_url") or data.get("previewUrl")
               or data.get("static_site_url") or data.get("staticSiteUrl"))
    if pid:
        print(f"\nProject: {pid}")
    if preview:
        print(f"Preview: {preview}")
    print("Status: building in the background (~5-13 min). Check the SA dashboard -> "
          "Website Studio, or run --status <project-id>.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", help="Source site URL to rebuild (clone modes)")
    ap.add_argument("--name", help="Project name (defaults to the domain)")
    ap.add_argument("--mode", default="clone_seo",
                    choices=["clone_seo", "clone", "free", "clone_ppc"])
    ap.add_argument("--prompt", "--user-prompt", dest="prompt",
                    help="Text prompt (free mode)")
    ap.add_argument("--campaign-id", dest="campaign_id", help="Campaign id (clone_ppc mode)")
    ap.add_argument("--key", help="SA API key (prefer the SA_MCP_API_KEY env var)")
    ap.add_argument("--dry-run", action="store_true", help="Print the request, send nothing")
    ap.add_argument("--list", action="store_true", help="List your Website Studio projects")
    ap.add_argument("--status", metavar="PROJECT_ID", help="Check a project's status")
    ap.add_argument("--credits", action="store_true", help="Show Website Studio credit status")
    ap.add_argument("--discover", action="store_true", help="Print the live create_project schema")
    args = ap.parse_args()

    key = args.key or os.environ.get("SA_MCP_API_KEY", "")

    if args.list:
        data, err = unwrap(call(key, "list_projects", {}))
        print(err or json.dumps(data, indent=2)); return
    if args.status:
        data, err = unwrap(call(key, "get_project", {"project_id": args.status}))
        print(err or json.dumps(data, indent=2)); return
    if args.credits:
        data, err = unwrap(call(key, "get_credit_status", {}))
        print(err or json.dumps(data, indent=2)); return
    if args.discover:
        # Golden rule: an empty create call makes the server return the real schema.
        obj = call(key, "create_project", {})
        _, err = unwrap(obj)
        print(err or json.dumps(obj, indent=2)); return

    # create_project
    name = args.name or (args.url.split("//")[-1].strip("/") if args.url else None)
    params = {"name": name, "mode": args.mode}
    if args.mode == "free":
        if not args.prompt:
            ap.error("--mode free needs --prompt")
        params["user_prompt"] = args.prompt
    elif args.mode == "clone_ppc":
        if not args.campaign_id:
            ap.error("--mode clone_ppc needs --campaign-id")
        params["campaign_id"] = args.campaign_id
    else:  # clone / clone_seo
        if not args.url:
            ap.error("clone modes need --url")
        params["source_url"] = args.url
    if not name:
        ap.error("need --name or --url")

    obj = call(key, "create_project", params, dry_run=args.dry_run)
    if obj is None:
        return  # dry-run already printed
    data, err = unwrap(obj)
    if err:
        print("Error from SearchAtlas:")
        print(json.dumps(err, indent=2) if isinstance(err, (dict, list)) else err)
        sys.exit(1)
    print(json.dumps(data, indent=2) if not isinstance(data, str) else data)
    summarize_project(data if isinstance(data, dict) else {})


if __name__ == "__main__":
    main()
