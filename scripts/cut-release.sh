#!/usr/bin/env bash
# cut-release.sh — cut a Foundry release in one deterministic, auditable command.
#
# Replaces release-please: no rolling release PR, no manifest state to desync, no
# special repo settings, no bolt-on alias mover. You run it locally when you decide
# to ship. It reads the current version from the latest git tag (the only source of
# truth), so it can't drift.
#
#   Usage:  bash scripts/cut-release.sh <major|minor|patch|X.Y.Z> [--dry-run]
#
# Preconditions: on `main`, clean tree, in sync with origin/main. Then it:
#   1. computes the new version from the latest vX.Y.Z tag,
#   2. builds a CHANGELOG section from conventional commits since that tag
#      (grouped feat/fix/other; BREAKING flagged) — only lastTag..HEAD, so the
#      rewritten-history duplicates release-please produced can't recur,
#   3. commits the CHANGELOG bump, tags vX.Y.Z, pushes both,
#   4. creates the GitHub release,
#   5. advances the floating major alias vN -> vX.Y.Z.
set -euo pipefail

BUMP="${1:?usage: cut-release.sh <major|minor|patch|X.Y.Z> [--dry-run]}"
DRY_RUN=false
[ "${2:-}" = "--dry-run" ] && DRY_RUN=true

die()  { echo "cut-release: $*" >&2; exit 1; }
step() { echo "== $* =="; }
run()  { if $DRY_RUN; then echo "  [dry-run] $*"; else eval "$@"; fi; }

require_clean_main() {
  [ "$(git rev-parse --abbrev-ref HEAD)" = "main" ] || die "not on main (checkout main first)"
  git diff --quiet && git diff --cached --quiet || die "working tree not clean"
  git fetch -q origin main
  [ "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)" ] || die "main is not in sync with origin/main"
}

current_version() { git describe --tags --abbrev=0 --match 'v[0-9]*.[0-9]*.[0-9]*' | sed 's/^v//'; }

next_version() { # <current> <bump>
  local bump="$2" IFS=. ; set -- $1 ; local maj=$1 min=$2 pat=$3
  case "$bump" in
    major) echo "$((maj+1)).0.0" ;;
    minor) echo "$maj.$((min+1)).0" ;;
    patch) echo "$maj.$min.$((pat+1))" ;;
  esac
}

# Resolve the target version + guard breaking-vs-bump.
resolve_version() { # <current> <bump-arg>
  local cur="$1" arg="$2"
  case "$arg" in
    major|minor|patch) next_version "$cur" "$arg" ;;
    [0-9]*.[0-9]*.[0-9]*) echo "$arg" ;;
    *) die "bump must be major | minor | patch | X.Y.Z" ;;
  esac
}

has_breaking() { # <lasttag>  — 0 if any breaking commit since lasttag
  git log "$1"..HEAD --no-merges --format='%s%n%b' | grep -qE '^[a-z]+([(].+[)])?!:|BREAKING CHANGE'
}

# Emit one "### <title>" block for commits whose subject matches <regex>, else nothing.
# awk regexes use [(] not \( — gawk warns on \( and other awks may treat it differently.
group() { # <lasttag> <regex> <title>
  local body
  body=$(git log "$1"..HEAD --no-merges --format='%h%x09%s' \
    | awk -F'\t' -v re="$2" '$2 ~ re { sub(/^[a-z]+([(].+[)])?!?: */, "", $2); print "* " $2 " (" $1 ")" }')
  [ -n "$body" ] && printf '\n### %s\n\n%s\n' "$3" "$body"
}

build_changelog_section() { # <lasttag> <newver> <repo>
  local last="$1" ver="$2" repo="$3" date
  date=$(date +%Y-%m-%d)
  printf '## [%s](https://github.com/%s/compare/%s...v%s) (%s)\n' "$ver" "$repo" "$last" "$ver" "$date"
  has_breaking "$last" && group "$last" '^[a-z]+([(].+[)])?!:' '⚠ BREAKING CHANGES'
  group "$last" '^feat([(].+[)])?!?:' 'Features'
  group "$last" '^fix([(].+[)])?!?:'  'Bug Fixes'
  echo
}

# Insert the new section directly above the first existing "## [" entry.
insert_changelog() { # <section-file>
  awk -v f="$1" '
    !done && /^## \[/ { while ((getline l < f) > 0) print l; done=1 }
    { print }
    END { if (!done) { while ((getline l < f) > 0) print l } }
  ' CHANGELOG.md > CHANGELOG.md.new && mv CHANGELOG.md.new CHANGELOG.md
}

main() {
  require_clean_main
  local repo cur ver last tag
  repo=$(gh repo view --json nameWithOwner -q .nameWithOwner)
  cur=$(current_version)
  ver=$(resolve_version "$cur" "$BUMP")
  last="v$cur" ; tag="v$ver"
  step "release $cur -> $ver"

  # Enforce semver: a breaking change since the last tag demands a major bump.
  if has_breaking "$last" && [ "${ver%%.*}" = "${cur%%.*}" ]; then
    die "breaking commits since $last but $ver is not a major bump — use 'major' or an explicit X.Y.Z"
  fi

  build_changelog_section "$last" "$ver" "$repo" > /tmp/cut-release-section.md
  echo "--- CHANGELOG section ---"; sed 's/^/  /' /tmp/cut-release-section.md

  run "insert_changelog /tmp/cut-release-section.md"
  run "git add CHANGELOG.md"
  run "git commit -m 'chore(release): $tag'"
  run "git tag '$tag'"
  run "git push origin main '$tag'"
  run "gh release create '$tag' --title '$tag' --notes-file /tmp/cut-release-section.md"

  step "advance the floating major alias v${ver%%.*} -> $tag"
  run "git tag -f 'v${ver%%.*}' '$tag^{}'"
  run "git push -f origin 'refs/tags/v${ver%%.*}'"

  echo "Done: $tag released; v${ver%%.*} alias updated."
}

# Only run when executed, not when sourced (so the helpers are unit-testable).
if [ "${BASH_SOURCE[0]:-$0}" = "$0" ]; then main; fi
