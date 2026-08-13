---
name: sa-website-studio
description: Push a website into SearchAtlas Website Studio — create a Website Studio project for a domain so it can be rebuilt as an AI-generated site in the SA dashboard. Use when someone wants to migrate or import a site into SearchAtlas, create a SearchAtlas Website Studio project, push their site into the SA landing page builder, or use SA to rebuild their website. Calls the SA MCP API (website_studio_tools → create_project). Requires an SA API key.
---

# SearchAtlas Website Studio — project creator

After extracting content off the old site, this is the step that registers the
domain in SearchAtlas Website Studio so the AI can rebuild it. It creates one
Website Studio project for a given domain by calling the SearchAtlas MCP server.

You (Claude) run this for the person. They are not technical — ask only for the
inputs listed below. Never make them touch a terminal or write JSON.

## What you need from them

| Input | What to ask | Notes |
|---|---|---|
| SA API key | "What is your SearchAtlas API key?" | They find it in the SA dashboard under **Settings → API Keys** → copy. Paste it exactly. |
| Domain / URL | "What is the website URL you want to migrate?" | e.g. `https://example.com` |
| Project name | "What should this project be called in SearchAtlas?" | Defaults to the domain if they don't care. |
| Mode | "Do you want SA to clone the live site's SEO signals, or start from scratch with a prompt?" | Almost always `clone_seo`. Only use `free` if the old site is down or unreachable. |

If they already gave you some of these, don't ask again.

## Keep the API key safe

The key is a secret — treat it like a password. Prefer passing it via the
environment so it never lands in shell history or logs:

```bash
export SA_MCP_API_KEY="<their key>"
```

The script reads `SA_MCP_API_KEY` automatically; `--key` is a fallback. Never echo
the key back, never write it to a file.

## How to use it

1. Collect the inputs above (key, URL, name, mode).
2. Run the bundled script (key from the environment):

   ```bash
   export SA_MCP_API_KEY="<their key>"
   python3 scripts/push-to-website-studio.py \
     --url "https://example.com" \
     --name "Example Site" \
     --mode clone_seo
   ```

   For `free` mode (old site is down), swap `--mode free --prompt "describe the site"`.

3. The script prints a JSON result. On success it returns the created project (id and,
   when available, a preview/static-site URL).

4. Tell them in plain language:
   - **Success:** "Your site has been registered in SearchAtlas Website Studio as
     project `<id>`. Website Studio is **building it now — that takes roughly 5–13
     minutes**. Log in to SearchAtlas → Website Studio and you'll see it there."
   - **No project id returned:** "It was accepted but SA didn't return an ID inline.
     Log in and look for a project named `<name>` in Website Studio."
   - **Error:** Tell them the error message and the most likely fix (see Troubleshooting).

5. Offer the natural next step: **"Want me to check the SEO signals on the new site
   once it's built?"** → that's the `migration-seo-parity` skill.

## What this does under the hood (for context, not to recite)

It POSTs a JSON-RPC 2.0 request to the SearchAtlas MCP endpoint
`https://mcp.searchatlas.com/api/v1/mcp`, calling the `website_studio_tools` tool with
the `create_project` operation:

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "website_studio_tools",
    "arguments": {
      "op": "create_project",
      "params": {
        "name": "Example Site",
        "mode": "clone_seo",
        "source_url": "https://example.com"
      }
    }
  }
}
```

Auth is an `X-API-KEY` header. The server may respond as plain JSON or a
Server-Sent-Events stream; the script handles both.

> **Auth note:** the `X-API-KEY` path is **confirmed working** — a valid key
> authenticates and reaches the tool. (A request with no/!valid key returns `401`
> with an "OAuth 2.1 authentication required" challenge; that's just the
> no-credential response, not a requirement to use OAuth.) Known issue: the
> SearchAtlas Website Studio backend can return a transient
> `{"success": false, "error_code": "INTERNAL", "is_transient": true}` on its ops
> (`create_project`, `list_projects`, …). That's an SA-side backend problem, not your
> key — retry later; if it persists, the SA Website Studio backend is the blocker.

`create_project` parameters (from the live MCP schema): `name` (required), `mode`
(`free` | `clone` | `clone_seo` | `clone_ppc`, default `free`), `user_prompt`
(required for `free`), `source_url` (required for clone modes), `campaign_id`
(required for `clone_ppc`). `clone_seo` crawls the live site and uses its SEO
structure as the foundation for the rebuild.

## Other things it can do

```bash
python3 scripts/push-to-website-studio.py --list                # list their Website Studio projects
python3 scripts/push-to-website-studio.py --status <project-id> # check build/generation status
python3 scripts/push-to-website-studio.py --credits            # remaining Website Studio credits
python3 scripts/push-to-website-studio.py --discover           # print the live create_project schema from the server
```

## Dry run (no API key yet, or no network)

```bash
python3 scripts/push-to-website-studio.py --url "https://example.com" --name "Example Site" --dry-run
```

Prints the exact request payload without contacting SA at all — good for a demo.

## Troubleshooting

| Error | Likely cause | Fix |
|---|---|---|
| `HTTP 401` / `403` / "Authentication failed" | Wrong/expired key, or the key lacks Website Studio scope | Copy a fresh key from SA Settings → API Keys; confirm the plan includes Website Studio |
| `HTTP 429` | Rate limited | The script retries up to 3 times; wait a minute and retry |
| `HTTP 500` / "Internal Server Error" on create | SA backend busy/credit check — known to happen on `create_project` | Not the key's fault. Retry; `--list` and `--status` still work. If it persists, the SA backend is the blocker |
| `no usable data frame` | Unexpected response format | Retry; if it persists check the SA status page |
| Project not appearing in dashboard | Created but still generating | It builds for several minutes — refresh Website Studio after a bit |

## What this does vs. what it isn't

This creates **one project** for **one domain**. That's the right starting point —
prove the API key works, see the project appear in the dashboard, watch the AI rebuild.

What it intentionally does **not** do — and where the automated service adds value:

- **Bulk-creating projects** for every domain in a portfolio at once, with
  deduplication (skipping domains already in SA).
- **Seeding each project** with the Markdown content already extracted from the old
  site, so SA rebuilds from structured content — not just whatever it can crawl.
- **Polling project status** after creation and notifying when the rebuilt site is ready.
- **Syncing content changes** — when the source site updates, re-running the full
  extraction + push pipeline automatically.

When someone has more than a handful of sites, or needs content seeding and status
polling wired into a workflow, that's the automated migration service.

<!-- DISTRIBUTOR: customize this line with your contact / booking link -->
> **Full-site migration pipeline with content seeding →** mailto:jonathan.duque@searchatlas.com

## Guardrails

- Only create projects for sites the person owns or is authorized to migrate.
- The API key is sensitive — never log it, never repeat it back, never include it in
  any output. Prefer the `SA_MCP_API_KEY` environment variable over `--key`.
- One project per run. "Do all my sites" → route to the full service above.
- This skill only creates projects. It does not modify or delete existing ones.
- Creating a project is asynchronous (minutes) — report it as "building," never "done."
