---
name: share-your-foundation
description: Package the rules, skills, and brand you built in Levels 1–3 into one repo a teammate — or your own second machine — clones and runs a single install command against, so everyone runs the exact same agent setup instead of reinventing it. Turns "here's my setup, good luck" into "clone this, run ./install.sh, you're me." Use when you want to onboard a teammate onto your agent stack, when your own setup won't follow you between machines (your CLAUDE.md / skills / brand kit live on one laptop and not the other), when you keep re-sending config over Slack, or when you're on Level 4 and the "share the foundation with your team" step has nothing runnable behind it.
---

# share-your-foundation

**The problem this solves:** you spent Levels 1–3 building a real foundation — the house
rules your agent follows (`CLAUDE.md`), the skills you wrote or adopted, the brand kit that
makes everything sound like *you*. Right now that foundation lives in one place: the machine
you built it on. A teammate who wants the same setup gets a Slack thread of "copy this file,
then install that, then paste these rules" — and ends up with a slightly-different, already-
drifting version of your stack. Worse, *you* hit the same wall between your own two machines:
the setup you rely on at your desk isn't the one on your laptop.

This skill fixes that with one move, borrowed from how software teams ship the same code to
every machine:

> **Put your foundation in one repo. A teammate clones it and runs one install command.
> An update is a pull, not a re-send.**

That's the whole thing. Your rules, your skills, your brand — one versioned repo, one command
to install, and everyone (including future-you on a new laptop) runs the *exact same* setup.

Why an owner should care, in money terms: every hour a new hire spends recreating your setup
by hand is an hour they're not billing, and every drifted copy is a client deliverable that
doesn't match your standard. A shared foundation means a new teammate is producing work to
*your* bar on day one, not week three — that's the offense. The consistency it buys is the
enabler underneath, not the headline.

---

## Say this to your agent

> "Package my agent foundation into one repo I can share. Take my house rules (my CLAUDE.md),
> my skills folder, and my brand kit, put them in a `my-foundation/` repo with a single
> `install.sh` that a teammate runs after cloning, and a README that explains the one command.
> Make updating it a git pull, not a re-send."

That one line is the whole ask. Below is what it actually builds.

---

## The 3-step setup

### Step 1 — Build the foundation repo

Run the bootstrapper once. It scaffolds a `my-foundation/` repo with the four things a
teammate needs and nothing they don't:

```bash
bash bootstrap.sh --out ./my-foundation
```

That creates:

```
my-foundation/
  CLAUDE.md          your house rules — the standards every agent run follows
  skills/            your skills (one folder per skill), the capabilities you built
  brand/             your brand kit — voice, audience, style, so output sounds like you
  install.sh         the ONE command a teammate runs after cloning
  README.md          "clone this, run ./install.sh" — the whole onboarding, one page
```

By default the bootstrapper drops in a starter `CLAUDE.md` and an empty `skills/` + `brand/`
for you to fill. If you already have a setup on this machine, point it at your real files and
it copies them in for you:

```bash
bash bootstrap.sh --out ./my-foundation \
  --claude ~/.claude/CLAUDE.md \
  --skills ~/.claude/skills \
  --brand  ~/brand-kit.md
```

**What good looks like:** open `my-foundation/` and everything a teammate would need to *be
you* is sitting in one folder — the rules, the skills, the brand — with a README that tells
them the single command to run. Nothing about your machine, your logins, or your clients is
in there (see the safety note below).

### Step 2 — Put it in a shared repo (the "share" part)

A folder on your laptop isn't shared — a repo is. Initialize it, commit, and push to wherever
your team already lives (GitHub, GitLab, a private repo — your call):

```bash
cd my-foundation
git init && git add -A && git commit -m "My agent foundation v1"
# push to your team's git host, then send the clone URL — that's the last time you "send" it
```

From now on, "sharing your setup" is sharing a clone URL once. When you improve a rule or add
a skill, you commit and push; your teammates (and your other machine) run `git pull` and
they're current. No more "which version of the CLAUDE.md are you on?"

### Step 3 — A teammate clones and runs one command

This is the payoff. Your teammate — or you, on a fresh machine — does exactly this:

```bash
git clone <your-foundation-repo-url> my-foundation
cd my-foundation
bash install.sh
```

`install.sh` installs your foundation into their agent, additively and safely:

- **Skills** are copied into their agent's skills directory (`~/.claude/skills/` by default) —
  purely additive, it never deletes skills they already have.
- **Your `CLAUDE.md`** is installed as their house rules — and if they already have one, the
  installer **backs it up to `CLAUDE.md.bak` first** and tells them, so nothing is lost.
- **Your brand kit** is placed where their agent can find it, so output sounds like your shop
  from the first run.

It prints exactly what it did and how to check it. Restart the agent, and the teammate is
running your exact foundation.

---

## What a good result looks like

- There's **one repo** that holds your rules + skills + brand, versioned in git.
- A teammate goes from nothing to *your exact setup* with **`git clone` + `bash install.sh`** —
  minutes, not a week of back-and-forth.
- An **update is a `git pull`**, not a re-send — you fix a rule once and everyone gets it.
- Your **own second machine** installs the same way: the setup finally follows you, instead of
  living on one laptop.
- Nothing private ships in the repo — no logins, no API keys, no client data (see below).

Concretely: you can hand the clone URL to a new hire on their first morning and by lunch their
agent produces work to your standard — because it *is* your standard, installed verbatim.

---

## The one thing to keep OUT of the repo (safety)

A shared foundation is your *standards*, not your *secrets*. Before you push, make sure the
repo contains **only** shareable config:

- **Never** commit API keys, tokens, `.env` files, or login/session files. The bootstrapper
  writes a `.gitignore` that blocks the common ones (`.env`, `*.key`, `credentials*`,
  `*.pem`), but you own the final check — skim the file list before your first commit.
- **Never** commit client data or anything under NDA. Brand kit = *your* voice/style, not a
  client's private material.
- Keep it to the four things: house rules, skills, brand, the installer. If you're unsure
  whether something belongs, it doesn't.

If your foundation must carry a secret to work (rare), the right pattern is an `.env.example`
with blank placeholders that the teammate fills in locally — the *shape* of the secret is
shared, never the secret itself.

---

## How this pairs with the other skills

- **`determinism-pattern`** — teaches "one skill per repeatable process, versioned in a shared
  repo, with a judge as the gate." This skill is that *shared repo*, made concrete: the place
  your versioned skills live so a fix reaches every machine and teammate on the next pull.
- **`brand-kit-from-url`** — builds the brand kit once. This skill is how that brand kit stops
  being yours alone and becomes your whole team's default voice.
- **`capability-map`** — shows what your stack can and can't do. Share the foundation and your
  teammate inherits the *whole* map, not a partial copy of it.
- **`host-your-agent`** — the same clone-and-install move that puts your foundation on a
  teammate's machine also stands your setup up on an always-on box you host the agent from.

---

## Where things land

| File | What it is |
|---|---|
| `bootstrap.sh` | Scaffolds the `my-foundation/` repo — pulls in your real `CLAUDE.md` / `skills/` / `brand` when you point at them, or drops starters. Writes the installer, README, and a secret-blocking `.gitignore`. |
| `templates/install.sh.template` | The installer that lands INSIDE the foundation repo — the one command a teammate runs after cloning. Additive skills install, backed-up `CLAUDE.md`, brand placement. |
| `templates/CLAUDE.md.example` | A starter house-rules file, used when you don't point at an existing one. |
| `templates/README.md.template` | The one-page "clone this, run ./install.sh" onboarding that ships in the foundation repo. |
| `templates/gitignore.template` | The secret-blocking `.gitignore` written into the foundation repo. |

Read `README.md` in this folder for the copy-paste quickstart.

---

## The rules it runs under (why the setup stays identical everywhere)

- **One repo is the one copy of the truth.** Rules, skills, brand — all in one versioned place;
  a fix reaches every machine and teammate on the next pull.
- **One command to install.** `git clone` + `bash install.sh`. If onboarding takes more than
  that, the foundation isn't packaged yet.
- **Additive and reversible.** Installing never deletes a teammate's existing skills, and it
  backs up any `CLAUDE.md` it replaces — nothing is lost.
- **Standards, not secrets.** Only shareable config goes in the repo; keys, sessions, and
  client data never do.

When those four things are true, "share your foundation with your team" stops being a Slack
thread and becomes a clone URL — which is exactly what Level 4 asks for.
