#!/usr/bin/env bash
# foundry-init — scaffold a repo onto the Foundry standard in one shot.
#
#   Usage:  bash foundry-init.sh <stack> [working_dir]
#     stack:        ts | java | php | kotlin | dotnet | python
#     working_dir:  where mise.toml/.habit-hooks live (default ".")
#   Env:
#     FOUNDRY_REF   foundry ref to pin the reusable workflows to (default "main";
#                   pass a tag or commit SHA to pin — recommended).
#
# Fetches the mise verb template, the habit-hooks config, the shared presets and
# the ruleset-guard script, then generates the caller workflows and prints the
# branch-protection checklist. Never overwrites an existing file — safe to re-run.
set -euo pipefail

STACK="${1:?stack required: ts | java | php | kotlin | dotnet | python}"
WD="${2:-.}"
REF="${FOUNDRY_REF:-main}"
REPO="CMaintz/foundry"
RAW="https://raw.githubusercontent.com/$REPO/$REF"

# HH = the habit-hooks preset basename (presets/habit-hooks/<HH>.toml). It tracks the
# plugin/language name, so `ts` maps to `typescript` — the others match the stack.
case "$STACK" in
  ts)     PLUGIN="habit-hooks-typescript"; CI="ts.yml";   HH="typescript" ;;
  java)   PLUGIN="habit-hooks-java";       CI="java.yml"; HH="java" ;;
  php)    PLUGIN="habit-hooks-php";        CI="php.yml";  HH="php" ;;
  kotlin|dotnet|python) PLUGIN=""; CI=""; HH="$STACK" ;;  # mise template only; inline gate
  *) echo "unknown stack: $STACK" >&2; exit 2 ;;
esac

fetch() { # fetch <remote-path> <local-path> — never clobber
  local rp="$1" lp="$2"
  if [ -e "$lp" ]; then echo "  skip (exists): $lp"; return 0; fi
  mkdir -p "$(dirname "$lp")"
  curl -fsSL "$RAW/$rp" -o "$lp" && echo "  wrote: $lp"
}

write() { # write <local-path> <<heredoc — never clobber
  local lp="$1"
  if [ -e "$lp" ]; then echo "  skip (exists): $lp"; cat >/dev/null; return 0; fi
  mkdir -p "$(dirname "$lp")"; cat > "$lp"; echo "  wrote: $lp"
}

echo "== Foundry scaffold: $STACK @ $REF =="

echo "- verbs + smells config"
fetch "mise/$STACK.toml" "$WD/mise.toml"
fetch "presets/habit-hooks/$HH.toml" "$WD/.habit-hooks/config.toml"

echo "- shared presets"
fetch "presets/gitleaks.toml" ".gitleaks.toml"
fetch "presets/renovate.json" "renovate.json"
fetch "scripts/ruleset_guard.py" "scripts/ruleset_guard.py"
if [ "$STACK" = "java" ]; then
  fetch "presets/pmd/ruleset.xml" "$WD/pmd/ruleset.xml"
  fetch "presets/pmd/no-var.xml" "$WD/config/pmd/no-var.xml"
  # Per-smell coaching guides (habit-hooks' project-override path) — the Java plugin
  # ships none, so without these every smell renders one generic message.
  for g in oversized-function high-complexity too-many-parameters deep-nesting; do
    fetch "presets/habit-hooks/java/guides/$g.md" "$WD/.habit-hooks/java/guides/$g.md"
  done
fi

# On Windows, tasks only run under bash if this is in GLOBAL mise config — mise
# refuses (and warns about) it in a project config for security. Set it once.
case "$(uname -s)" in
  MINGW*|MSYS*|CYGWIN*)
    if command -v mise >/dev/null 2>&1; then
      mise settings set windows_default_inline_shell_args "bash -c" 2>/dev/null \
        && echo "  set global mise: windows_default_inline_shell_args = bash -c"
    fi ;;
esac

echo "- GitHub labels (ticket state machine + gate controls)"
if command -v gh >/dev/null 2>&1 && gh repo view >/dev/null 2>&1; then
  fetch "scripts/setup-labels.sh" "scripts/setup-labels.sh"
  bash scripts/setup-labels.sh || echo "  (skipped — check \`gh auth status\`)"
else
  echo "  skip: no gh / no GitHub remote yet — run scripts/setup-labels.sh once you have one"
fi

echo "- caller workflows (pinned to $REF)"
if [ -n "$CI" ]; then
  write ".github/workflows/gate.yml" <<YAML
name: gate
on: { pull_request: {}, push: { branches: [main] } }
concurrency: { group: gate-\${{ github.ref }}, cancel-in-progress: true }
jobs:
  gate:
    uses: $REPO/.github/workflows/$CI@$REF
    with:
      working_directory: "$WD"
YAML
else
  write ".github/workflows/gate.yml" <<YAML
name: gate
on: { pull_request: {}, push: { branches: [main] } }
concurrency: { group: gate-\${{ github.ref }}, cancel-in-progress: true }
permissions: { contents: read }
jobs:
  gate:
    name: Deterministic gate
    runs-on: ubuntu-latest
    defaults: { run: { working-directory: "$WD" } }
    steps:
      - uses: actions/checkout@v5
      - uses: jdx/mise-action@v3
      # No reusable $STACK workflow yet — run the six-verb gate directly.
      - run: mise run gate
YAML
fi

write ".github/workflows/security.yml" <<YAML
name: security
on: { pull_request: {}, push: { branches: [main] } }
concurrency: { group: security-\${{ github.ref }}, cancel-in-progress: true }
jobs:
  tier0:
    uses: $REPO/.github/workflows/tier0.yml@$REF
  sast:
    uses: $REPO/.github/workflows/semgrep.yml@$REF
YAML

write ".github/workflows/ratchet.yml" <<YAML
name: ratchet
on: { pull_request: {} }
jobs:
  ratchet:
    uses: $REPO/.github/workflows/ratchet-report.yml@$REF
    permissions: { contents: read, pull-requests: write }
YAML

if [ -n "$PLUGIN" ]; then
  write ".github/workflows/bootstrap.yml" <<YAML
name: bootstrap
on:
  workflow_dispatch: {}
  schedule:
    - cron: '0 6 * * *'   # daily auto-prune — baseline shrinks on its own, one PR/day max
jobs:
  bootstrap:
    uses: $REPO/.github/workflows/bootstrap.yml@$REF
    with:
      working_directory: "$WD"
      habit_hooks_plugin: "$PLUGIN"
    permissions: { contents: write, pull-requests: write }
YAML
fi

cat <<'NEXT'

== Next steps ==
1. Pin versions: set the tool versions in mise.toml and, ideally, re-run with
   FOUNDRY_REF=<a tag or SHA> so the reusable workflows are pinned, not floating on main.
2. Install the detectors and generate the smell baseline: run the `bootstrap`
   workflow once (Actions tab -> bootstrap -> Run workflow). It opens a PR with
   .habit-hooks/snooze.json. NB: some sensors ship DISABLED (opt-in) — e.g. jscpd
   duplication for java, since it needs Node. Skim .habit-hooks/config.toml for
   `[sensors.*] disabled = true` and turn on the ones you can support, so coverage
   isn't silently narrower than you think.
3. Turn on Renovate (or Dependabot) so the pins you just set stay fresh.
4. Branch protection on `main` (Settings -> Branches), require these checks:
     - Deterministic gate            (gate.yml)
     - Secret scan, Ruleset guard    (security.yml / tier0)
     - SAST                          (security.yml / semgrep)
     - Structural smells             (once a baseline exists)
   Gotchas: required-check names must match the job name EXACTLY; do NOT require
   the workflow_dispatch `bootstrap` job; enable "require branches up to date".
5. Commit, open a PR, and confirm the gate is green from a clean tree.
NEXT
echo "Done."
