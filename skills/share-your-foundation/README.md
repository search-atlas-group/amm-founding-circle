# share-your-foundation

Package the rules, skills, and brand you built in Levels 1–3 into **one repo** a
teammate — or your own second machine — clones and runs a single install command
against. Everyone ends up on the *exact same* agent setup instead of reinventing it.
An update is a `git pull`, not a re-send.

Read `SKILL.md` for the full walkthrough and the "say this to your agent" line.
This README is the copy-paste quickstart.

This is the runnable behind **Level 4, step 3** ("share the foundation with your
team") — the one step on that rung that used to have nothing to actually *do*.

## Quickstart (share your setup in 3 minutes)

```bash
# 1. Build the foundation repo. Point it at your real files, or let it drop starters.
bash bootstrap.sh --out ./my-foundation \
  --claude ~/.claude/CLAUDE.md \
  --skills ~/.claude/skills \
  --brand  ~/brand-kit.md

# 2. Make it a shared repo (the "share" part) and push it once.
cd my-foundation
git init && git add -A && git commit -m "My agent foundation v1"
# push to your team's git host, then send the clone URL — the last time you "send" it.

# 3. A teammate (or you, on a new machine) gets your exact setup:
git clone <your-foundation-repo-url> my-foundation
cd my-foundation
bash install.sh
# restart the agent — they're now running your foundation.
```

## What ends up in the repo

```
my-foundation/
  CLAUDE.md      your house rules — the standard every run follows
  skills/        your skills (one folder each) — the capabilities you built
  brand/         your brand kit — voice, audience, style
  install.sh     the ONE command a teammate runs after cloning
  README.md      the one-page onboarding
  .gitignore     blocks secrets from ever being committed
```

## What `install.sh` does on the teammate's machine

- **Skills** → copied into `~/.claude/skills/` (override with `CLAUDE_SKILLS_TARGET`).
  Purely additive — never deletes skills they already have.
- **CLAUDE.md** → installed as their house rules; any existing one is **backed up to
  `CLAUDE.md.bak` first**, and the installer says so.
- **brand/** → placed where the agent can find it, so output sounds like your shop.
- Prints exactly what it did + how to verify.

## The one rule: standards, not secrets

Only shareable config goes in the repo — house rules, skills, brand, the installer.
**Never** commit API keys, `.env` files, tokens, session/login files, or client data.
The bootstrapper writes a `.gitignore` that blocks the common ones (`.env`, `*.key`,
`credentials*`, `*.pem`) — but skim the file list before your first commit anyway.
If your foundation needs a secret to run, ship an `.env.example` with blank
placeholders, never the real value.

## How it pairs

- **`determinism-pattern`** — "versioned in a shared repo" made concrete; this is that repo.
- **`brand-kit-from-url`** — builds the brand kit; this shares it team-wide.
- **`host-your-agent`** — the same clone-and-install stands your setup up on an always-on box.

## Files

```
share-your-foundation/
  SKILL.md                       the walkthrough (read this first)
  README.md                      this quickstart
  bootstrap.sh                   scaffolds the foundation repo from your setup
  templates/
    install.sh.template          the installer that ships inside the foundation repo
    CLAUDE.md.example            starter house rules (when you don't supply your own)
    README.md.template           the foundation repo's own one-page onboarding
    gitignore.template           the secret-blocking .gitignore
```
