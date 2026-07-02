#!/usr/bin/env bash
# AMM MCP Day Skill Pack — installer
# Copies (or symlinks) each skill into Claude's skills directory.
#
# Default target: ~/.claude/skills/
# Override:       CLAUDE_SKILLS_TARGET=/some/path bash install.sh
# Symlink mode:   USE_SYMLINKS=1 bash install.sh  (faster updates if you `git pull` later)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# The skill folders live alongside this script (skills/<name>/), so the source
# is this directory itself. (Older layout placed install.sh one level up.)
SKILLS_SRC="$SCRIPT_DIR"
TARGET="${CLAUDE_SKILLS_TARGET:-$HOME/.claude/skills}"
USE_SYMLINKS="${USE_SYMLINKS:-0}"

GREEN='\033[0;32m'
DIM='\033[2m'
NC='\033[0m'

if [ ! -d "$SKILLS_SRC" ]; then
  echo "ERROR: skills directory not found at $SKILLS_SRC"
  exit 1
fi

mkdir -p "$TARGET"

echo ""
echo "  AMM MCP Day Skill Pack"
echo -e "  ${DIM}Installing to: $TARGET${NC}"
echo ""

count=0
for skill_dir in "$SKILLS_SRC"/*/; do
  skill_name="$(basename "$skill_dir")"
  dest="$TARGET/$skill_name"

  if [ -e "$dest" ] || [ -L "$dest" ]; then
    rm -rf "$dest"
  fi

  if [ "$USE_SYMLINKS" = "1" ]; then
    ln -s "$skill_dir" "$dest"
    echo -e "  ${GREEN}↳${NC} $skill_name ${DIM}(symlink)${NC}"
  else
    cp -R "$skill_dir" "$dest"
    echo -e "  ${GREEN}✓${NC} $skill_name"
  fi
  count=$((count + 1))
done

echo ""
echo -e "  ${GREEN}Done.${NC} $count skills installed."
echo ""
echo "  Restart Claude Code (or refresh your Claude session) and the skills"
echo "  will be available. Try one of:"
echo ""
echo "    \"Audit how visible Acme is in AI answers for these prompts: …\""
echo "      → triggers llm-citation-audit"
echo ""
echo "    \"Build a content brief for the keyword 'best plumber miami'\""
echo "      → triggers content-brief-generator"
echo ""
echo "    \"Map the entity gaps for Acme's category\""
echo "      → triggers entity-topical-authority-mapper"
echo ""
