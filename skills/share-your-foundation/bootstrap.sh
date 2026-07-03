#!/usr/bin/env bash
# ============================================================================
#  share-your-foundation — bootstrapper
#
#  Scaffolds a "foundation repo" — one folder that holds your agent house rules,
#  skills, and brand kit, plus the single install command a teammate runs after
#  cloning. Point it at your real files, or let it drop starters you fill in.
#
#    bash bootstrap.sh --out ./my-foundation
#    bash bootstrap.sh --out ./my-foundation \
#        --claude ~/.claude/CLAUDE.md \
#        --skills ~/.claude/skills \
#        --brand  ~/brand-kit.md
#
#  It does NOT git-init or push — that's yours (the README prints the commands).
#  It writes a .gitignore that blocks common secrets, but skim the file list
#  before your first commit anyway: standards go in the repo, secrets never do.
# ============================================================================

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATES="$HERE/templates"

GREEN='\033[0;32m'; DIM='\033[2m'; YELLOW='\033[0;33m'; NC='\033[0m'

OUT="./my-foundation"
CLAUDE_SRC=""
SKILLS_SRC=""
BRAND_SRC=""

usage() { sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//'; exit "${1:-0}"; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --out)     OUT="${2:-}"; shift 2 ;;
    --claude)  CLAUDE_SRC="${2:-}"; shift 2 ;;
    --skills)  SKILLS_SRC="${2:-}"; shift 2 ;;
    --brand)   BRAND_SRC="${2:-}"; shift 2 ;;
    -h|--help) usage 0 ;;
    *) echo "unknown flag: $1" >&2; usage 2 ;;
  esac
done

# Expand a leading ~ so paths like ~/.claude/CLAUDE.md work when quoted.
expand_tilde() { case "$1" in "~"|"~/"*) echo "${1/#\~/$HOME}";; *) echo "$1";; esac; }
OUT="$(expand_tilde "$OUT")"
[[ -n "$CLAUDE_SRC" ]] && CLAUDE_SRC="$(expand_tilde "$CLAUDE_SRC")"
[[ -n "$SKILLS_SRC" ]] && SKILLS_SRC="$(expand_tilde "$SKILLS_SRC")"
[[ -n "$BRAND_SRC"  ]] && BRAND_SRC="$(expand_tilde "$BRAND_SRC")"

if [[ -e "$OUT" ]]; then
  echo "ERROR: $OUT already exists. Choose a fresh --out path (won't overwrite)." >&2
  exit 1
fi

echo ""
echo "  Building your foundation repo at: $OUT"
mkdir -p "$OUT/skills" "$OUT/brand"

# --- CLAUDE.md: your real one if given, else the starter ---------------------
if [[ -n "$CLAUDE_SRC" ]]; then
  [[ -f "$CLAUDE_SRC" ]] || { echo "ERROR: --claude file not found: $CLAUDE_SRC" >&2; exit 1; }
  cp "$CLAUDE_SRC" "$OUT/CLAUDE.md"
  echo -e "  ${GREEN}✓${NC} CLAUDE.md  ${DIM}(from $CLAUDE_SRC)${NC}"
else
  cp "$TEMPLATES/CLAUDE.md.example" "$OUT/CLAUDE.md"
  echo -e "  ${GREEN}✓${NC} CLAUDE.md  ${DIM}(starter — edit it to your house rules)${NC}"
fi

# --- skills/: copy your skills in if given -----------------------------------
if [[ -n "$SKILLS_SRC" ]]; then
  [[ -d "$SKILLS_SRC" ]] || { echo "ERROR: --skills dir not found: $SKILLS_SRC" >&2; exit 1; }
  copied=0
  for d in "$SKILLS_SRC"/*/; do
    [[ -d "$d" ]] || continue
    # Follow symlinks (skills are often symlinked into ~/.claude/skills).
    cp -RL "$d" "$OUT/skills/$(basename "$d")"
    copied=$((copied + 1))
  done
  echo -e "  ${GREEN}✓${NC} skills/    ${DIM}($copied skill folder(s) from $SKILLS_SRC)${NC}"
else
  cat > "$OUT/skills/README.md" <<'EOF'
# skills

Drop one folder per skill here (each with its own `SKILL.md`). These are the
capabilities a teammate inherits when they run `../install.sh`. Re-run the
bootstrapper with `--skills ~/.claude/skills` to pull your existing skills in.
EOF
  echo -e "  ${GREEN}✓${NC} skills/    ${DIM}(empty — add one folder per skill, or re-run with --skills)${NC}"
fi

# --- brand/: copy your brand kit in if given ---------------------------------
if [[ -n "$BRAND_SRC" ]]; then
  if [[ -f "$BRAND_SRC" ]]; then
    cp "$BRAND_SRC" "$OUT/brand/$(basename "$BRAND_SRC")"
  elif [[ -d "$BRAND_SRC" ]]; then
    cp -RL "$BRAND_SRC"/. "$OUT/brand/"
  else
    echo "ERROR: --brand path not found: $BRAND_SRC" >&2; exit 1
  fi
  echo -e "  ${GREEN}✓${NC} brand/     ${DIM}(from $BRAND_SRC)${NC}"
else
  cat > "$OUT/brand/brand-kit.md" <<'EOF'
# Brand kit

Your voice, audience, and style — so every agent run sounds like your shop, not a
generic bot. Fill this in (or generate it with the `brand-kit-from-url` skill) and
your whole team inherits the same voice on the first run.

- **Voice / tone:**
- **Audience:**
- **Things we always do:**
- **Things we never do:**
- **Key phrases / vocabulary:**
EOF
  echo -e "  ${GREEN}✓${NC} brand/     ${DIM}(starter brand-kit.md — fill it in)${NC}"
fi

# --- the installer + README + .gitignore that ship inside the repo -----------
cp "$TEMPLATES/install.sh.template" "$OUT/install.sh"
chmod +x "$OUT/install.sh"
cp "$TEMPLATES/README.md.template" "$OUT/README.md"
cp "$TEMPLATES/gitignore.template" "$OUT/.gitignore"
echo -e "  ${GREEN}✓${NC} install.sh + README.md + .gitignore"

echo ""
echo -e "  ${GREEN}Done.${NC} Your foundation repo is at $OUT"
echo ""
echo "  Next — make it shared (this is the last time you 'send' it):"
echo -e "    ${DIM}cd $OUT${NC}"
echo -e "    ${DIM}# skim the file list first — standards go in, secrets never do${NC}"
echo -e "    ${DIM}git init && git add -A && git commit -m \"My agent foundation v1\"${NC}"
echo -e "    ${DIM}# push to your team's git host, then share the clone URL${NC}"
echo ""
echo "  A teammate then runs:  git clone <url> && cd <repo> && bash install.sh"
echo ""
echo -e "  ${YELLOW}Before you commit:${NC} open the folder and confirm there are no keys,"
echo "  .env files, tokens, or client data in it. Share standards, not secrets."
echo ""
