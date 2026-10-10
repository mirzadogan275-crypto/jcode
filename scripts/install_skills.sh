#!/usr/bin/env bash
# Install third-party agent skill packs into a jcode skills directory.
#
# Each pack is a GitHub repo containing `<name>/SKILL.md` skill folders.
# Skills are copied flat into the destination (`<dest>/<skill-name>/SKILL.md`),
# which is the layout jcode's skill registry scans.
#
# Usage:
#   scripts/install_skills.sh [--global | --dest DIR] [PACK...]
#
#   --global     install into ~/.jcode/skills (available in every project)
#   --dest DIR   install into DIR (default: <repo>/.jcode/skills)
#   PACK         one or more pack ids (default: all). See `--list`.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
dest="$repo_root/.jcode/skills"

# id|repo|skills path inside repo ("." = repo root is a single skill)
PACKS=(
  "marketingskills|coreyhaines31/marketingskills|skills"
  "stop-slop|hardikpandya/stop-slop|."
  "ui-ux-pro-max|nextlevelbuilder/ui-ux-pro-max-skill|.claude/skills"
  "remotion|remotion-dev/skills|skills"
  "context-engineering|muratcankoylan/Agent-Skills-for-Context-Engineering|skills"
)

usage() { sed -n '2,14p' "$0" | sed 's/^# \{0,1\}//'; }

selected=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --global) dest="$HOME/.jcode/skills"; shift ;;
    --dest) dest="$2"; shift 2 ;;
    --list)
      for p in "${PACKS[@]}"; do IFS='|' read -r id repo _ <<<"$p"; echo "$id  (github.com/$repo)"; done
      exit 0 ;;
    -h|--help) usage; exit 0 ;;
    *) selected+=("$1"); shift ;;
  esac
done

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$dest"

install_skill_dir() {
  local src="$1" name
  name="$(basename "$src")"
  rm -rf "${dest:?}/$name"
  cp -RL "$src" "$dest/$name"
  rm -rf "$dest/$name/.git"
  echo "  + $name"
}

for p in "${PACKS[@]}"; do
  IFS='|' read -r id repo path <<<"$p"
  if [[ ${#selected[@]} -gt 0 && ! " ${selected[*]} " =~ " $id " ]]; then
    continue
  fi
  echo "==> $id (github.com/$repo)"
  git clone -q --depth 1 "https://github.com/$repo.git" "$tmp/$id"
  if [[ "$path" == "." ]]; then
    # Single-skill repo: the repo root is the skill folder.
    rm -rf "$tmp/$id/.git"
    mv "$tmp/$id" "$tmp/$id.skill"
    mkdir -p "$tmp/$id"
    local_name="$(sed -n 's/^name:[[:space:]]*//p' "$tmp/$id.skill/SKILL.md" | head -1)"
    mv "$tmp/$id.skill" "$tmp/$id/${local_name:-$id}"
    path="."
  fi
  for skill_md in "$tmp/$id/$path"/*/SKILL.md; do
    [[ -f "$skill_md" ]] || continue
    install_skill_dir "$(dirname "$skill_md")"
  done
done

echo "Installed into $dest"
