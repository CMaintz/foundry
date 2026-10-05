#!/usr/bin/env bash
# foundry-init - scaffold a repo onto the Foundry standard in one shot.
#
#   Usage:  bash foundry-init.sh <stack> [working_dir]          # single package
#           bash foundry-init.sh --mono <stack:dir> [<stack:dir>...]   # monorepo
#     stack:        ts | java | php | kotlin | dotnet | python
#                   (--mono supports the facade stacks only: ts | java | php | dotnet)
#     working_dir:  where mise.toml/.habit-hooks live (default ".")
#   Env:
#     FOUNDRY_REF   foundry ref to pin the reusable workflows to (default "main";
#                   pass a tag or commit SHA to pin - recommended).
#     FOUNDRY_RAW   base URL the templates are fetched from (default: raw GitHub at
#                   FOUNDRY_REF). The CI smoke test points it at a local checkout (file://).
#
# Fetches the mise verb template, the habit-hooks config, the shared presets and the
# ruleset-guard script, then generates the caller workflows and prints the
# branch-protection checklist. In --mono mode it scaffolds each package and emits one
# gate.yml that fans out per package behind the changes.yml path classifier, wrapped in
# a single `gate-ok`. Never overwrites an existing file - safe to re-run.
set -euo pipefail

REF="${FOUNDRY_REF:-main}"
REPO="CMaintz/foundry"
RAW="${FOUNDRY_RAW:-https://raw.githubusercontent.com/$REPO/$REF}"

fetch() { # fetch <remote-path> <local-path> - never clobber
  local rp="$1" lp="$2"
  if [ -e "$lp" ]; then echo "  skip (exists): $lp"; return 0; fi
  mkdir -p "$(dirname "$lp")"
  curl -fsSL "$RAW/$rp" -o "$lp" && echo "  wrote: $lp"
}

write() { # write <local-path> <<heredoc - never clobber
  local lp="$1"
  if [ -e "$lp" ]; then echo "  skip (exists): $lp"; cat >/dev/null; return 0; fi
  mkdir -p "$(dirname "$lp")"; cat > "$lp"; echo "  wrote: $lp"
}

# resolve_stack <stack> - sets R_PLUGIN (habit-hooks plugin; "" if none), R_CI (per-stack
# facade marker; "" for inline stacks) and R_HH (habit-hooks preset basename). HH tracks
# the plugin/language name, so `ts` maps to `typescript`; the others match the stack.
resolve_stack() {
  case "$1" in
    ts)     R_PLUGIN="habit-hooks-typescript"; R_CI="ts.yml";     R_HH="typescript" ;;
    java)   R_PLUGIN="habit-hooks-java";       R_CI="java.yml";   R_HH="java" ;;
    php)    R_PLUGIN="habit-hooks-php";         R_CI="php.yml";    R_HH="php" ;;
    dotnet) R_PLUGIN="habit-hooks-generic";     R_CI="dotnet.yml"; R_HH="dotnet" ;;
    python) R_PLUGIN="habit-hooks-generic";     R_CI="python.yml"; R_HH="python" ;;  # facade gate
    kotlin) R_PLUGIN=""; R_CI=""; R_HH="kotlin" ;;  # mise template only; inline gate
    *) echo "unknown stack: $1" >&2; exit 2 ;;
  esac
}

# mono_jobid <dir> - a workflow-safe job id for a package dir (job ids forbid / and .).
mono_jobid() { printf '%s' "$1" | tr '/.' '--'; }

fetch_package_core() { # <stack> <wd> - verbs, smells config, loop telemetry scripts
  local stack="$1" wd="$2"
  resolve_stack "$stack"
  fetch "mise/$stack.toml" "$wd/mise.toml"
  fetch "presets/habit-hooks/$R_HH.toml" "$wd/.habit-hooks/config.toml"
  # Loop telemetry lives in $wd/scripts (= config_root/scripts, on PATH via the mise
  # template), NOT repo-root scripts/ - a package with wd=backend must find them too.
  fetch "scripts/foundry-verb-wrap" "$wd/scripts/foundry-verb-wrap"
  fetch "scripts/foundry-loop-report" "$wd/scripts/foundry-loop-report"
  chmod +x "$wd/scripts/foundry-verb-wrap" "$wd/scripts/foundry-loop-report" 2>/dev/null || true
}

# ensure_ts_devdeps <wd> - add the structural-smell sensor tools to the consumer's
# devDependencies if absent, so the habit-hooks typescript (knip, ts-morph) and generic
# (jscpd) sensors seed against real findings instead of a missing-tool error. Caret-pinned;
# Renovate bumps them. Never overwrites an existing pin; no-ops with a NOTE when there's no
# package.json yet (bootstrap also `npm ci`s + PATHs node_modules/.bin before seeding).
ensure_ts_devdeps() {
  local wd="$1" nv name have
  if [ ! -f "$wd/package.json" ]; then
    echo "  NOTE: no $wd/package.json - add knip, ts-morph, jscpd to devDependencies so the TS smell sensors run"
    return 0
  fi
  if ! command -v npm > /dev/null 2>&1; then
    echo "  NOTE: npm not on PATH - add knip, ts-morph, jscpd to devDependencies so the TS smell sensors run"
    return 0
  fi
  for nv in "knip@^6.39.0" "ts-morph@^28.0.0" "jscpd@^5.4.0"; do
    name="${nv%@*}"
    have="$( (cd "$wd" && npm pkg get "devDependencies.$name") 2>/dev/null || true)"
    case "$have" in
      ''|'{}'|'undefined')
        if ( cd "$wd" && npm pkg set "devDependencies.$name=${nv#*@}" ); then
          echo "  devDep: $name ${nv#*@}"
        else echo "  WARN: could not add devDep $name (add it manually)"; fi ;;
      *) echo "  skip devDep (present): $name" ;;
    esac
  done
}

fetch_ts_extras() { # <wd> - strict tsconfig + ratcheted npm-audit + jscpd ignores + smell devDeps
  local wd="$1"
  # `typecheck` refuses to run without a tsconfig: framework checkers (astro check,
  # vue-tsc) otherwise exit 0 having checked only their own file types. A repo that
  # already has one keeps it (fetch never clobbers); make its `include` cover scripts/tests.
  fetch "presets/typecheck/tsconfig.json" "$wd/tsconfig.json"
  if [ -d supabase/functions ] || [ -d "$wd/supabase/functions" ]; then
    echo "  NOTE: supabase/functions found - set FOUNDRY_DENO_PATHS and pin deno in mise.toml"
  fi
  fetch "scripts/npm-audit-ratchet.mjs" "$wd/scripts/npm-audit-ratchet.mjs"
  fetch "scripts/foundry-flaky" "$wd/scripts/foundry-flaky"
  chmod +x "$wd/scripts/foundry-flaky" 2>/dev/null || true
  # jscpd duplication (generic sensor) reads .jscpd.json; pre-place it like the Java path.
  fetch "presets/habit-hooks/jscpd.json" "$wd/.jscpd.json"
  ensure_ts_devdeps "$wd"
}

fetch_java_extras() { # <wd> - PMD ruleset, jscpd ignore list, per-smell coaching guides
  local wd="$1" g
  fetch "presets/lint/pmd/ruleset.xml" "$wd/pmd/ruleset.xml"
  fetch "presets/lint/pmd/no-var.xml" "$wd/config/pmd/no-var.xml"
  # jscpd ignore list, inert while jscpd is disabled but pre-placed so enabling
  # duplication detection does not first gate test code.
  fetch "presets/habit-hooks/jscpd.json" "$wd/.jscpd.json"
  # Per-smell coaching (the Java plugin ships none, so without these every smell
  # renders one generic message).
  for g in oversized-function high-complexity too-many-parameters deep-nesting; do
    fetch "presets/habit-hooks/java/guides/$g.md" "$wd/.habit-hooks/java/guides/$g.md"
  done
}

scaffold_package() { # <stack> <wd> - everything one package needs (not repo-level)
  local stack="$1" wd="$2"
  echo "- package: $stack @ $wd"
  fetch_package_core "$stack" "$wd"
  if [ "$stack" = ts ]; then fetch_ts_extras "$wd"; fi
  if [ "$stack" = java ]; then fetch_java_extras "$wd"; fi
}

ensure_gitignore() { # the telemetry log is local-only observability, never committed
  if [ ! -f .gitignore ]; then
    printf '# Foundry loop telemetry (local observability)\n.foundry/\n' > .gitignore
    echo "  wrote: .gitignore (+.foundry/)"
  elif ! grep -qxF '.foundry/' .gitignore 2>/dev/null; then
    printf '\n# Foundry loop telemetry (local observability)\n.foundry/\n' >> .gitignore
    echo "  updated: .gitignore (+.foundry/)"
  fi
}

set_windows_mise_shell() { # tasks only run under bash if this is in GLOBAL mise config
  case "$(uname -s)" in
    MINGW*|MSYS*|CYGWIN*)
      if command -v mise >/dev/null 2>&1 \
        && mise settings set windows_default_inline_shell_args "bash -c" 2>/dev/null; then
        echo "  set global mise: windows_default_inline_shell_args = bash -c"
      fi ;;
  esac
}

setup_labels() { # the GitHub labels the workflows + ticket state machine need
  echo "- GitHub labels (ticket state machine + gate controls)"
  if command -v gh >/dev/null 2>&1 && gh repo view >/dev/null 2>&1; then
    fetch "scripts/setup-labels.sh" "scripts/setup-labels.sh"
    bash scripts/setup-labels.sh || echo "  (skipped - check \`gh auth status\`)"
  else
    echo "  skip: no gh / no GitHub remote yet - run scripts/setup-labels.sh once you have one"
  fi
}

repo_level_once() { # shared presets + repo-wide setup that runs once, not per package
  echo "- shared presets"
  fetch "presets/security/gitleaks.toml" ".gitleaks.toml"
  fetch "presets/renovate.json" "renovate.json"
  fetch "scripts/ruleset_guard.py" "scripts/ruleset_guard.py"
  # One-shot, non-blocking PR check reporter the pr-ci-watch flow calls once CI has
  # finished. Repo-scoped (gh pr checks on the branch's PR), so it lands once at repo
  # root, not per package.
  fetch "scripts/foundry-pr-report" "scripts/foundry-pr-report"
  chmod +x scripts/foundry-pr-report 2>/dev/null || true
  ensure_gitignore
  set_windows_mise_shell
  setup_labels
}

emit_security_and_ratchet() { # repo-level facades, identical single or mono
  write ".github/workflows/security.yml" <<YAML
name: security
on: { pull_request: {}, push: { branches: [main] } }
concurrency:
  group: security-\${{ github.ref }}
  cancel-in-progress: true
jobs:
  security:
    uses: $REPO/.github/workflows/security.yml@$REF   # facade: secret scan + ruleset-guard + SAST
    permissions: { contents: read, pull-requests: read }   # the secret scan lists the PR's commits
YAML
  write ".github/workflows/ratchet.yml" <<YAML
name: ratchet
on: { pull_request: {} }
jobs:
  ratchet:
    uses: $REPO/.github/workflows/ratchet-report.yml@$REF
    permissions: { contents: read, pull-requests: write }
YAML
}

emit_single_gate() { # <stack> <wd> - facade call, or inline gate for kotlin
  local stack="$1" wd="$2"
  if [ -n "$R_CI" ]; then
    write ".github/workflows/gate.yml" <<YAML
name: gate
on: { pull_request: {}, push: { branches: [main] } }
concurrency:
  group: gate-\${{ github.ref }}
  cancel-in-progress: true
jobs:
  gate:
    uses: $REPO/.github/workflows/gate.yml@$REF   # the public facade - pin this, not the per-stack files
    with:
      stack: "$stack"
      working_directory: "$wd"
YAML
  else
    write ".github/workflows/gate.yml" <<YAML
name: gate
on: { pull_request: {}, push: { branches: [main] } }
concurrency:
  group: gate-\${{ github.ref }}
  cancel-in-progress: true
permissions: { contents: read }
jobs:
  gate:
    name: Deterministic gate
    runs-on: ubuntu-latest
    defaults: { run: { working-directory: "$wd" } }
    steps:
      - uses: actions/checkout@v5
      - uses: jdx/mise-action@v3
      # No reusable $stack workflow yet - run the six-verb gate directly.
      - run: mise run gate
YAML
  fi
}

emit_single_bootstrap() { # <plugin> <wd>
  write ".github/workflows/bootstrap.yml" <<YAML
name: bootstrap
on:
  workflow_dispatch: {}
  schedule:
    - cron: '0 6 * * *'   # daily auto-prune - baseline shrinks on its own, one PR/day max
jobs:
  bootstrap:
    uses: $REPO/.github/workflows/bootstrap.yml@$REF
    with:
      working_directory: "$2"
      habit_hooks_plugin: "$1"
    permissions: { contents: write, pull-requests: write }
YAML
}

gen_mono_gate_pkg() { # <stack> <dir> - one per-package facade call, path-filtered
  local stack="$1" dir="$2" jobid; jobid="$(mono_jobid "$dir")"
  cat <<YAML
  $jobid:
    needs: changes
    if: contains(fromJSON(needs.changes.outputs.changes), '$dir')
    uses: $REPO/.github/workflows/gate.yml@$REF
    with:
      stack: $stack
      working_directory: $dir
YAML
}

gen_mono_gate_ok() { # <pair...> - the single required check, over every package job
  local pair needs="changes"
  for pair in "$@"; do needs+=", $(mono_jobid "${pair#*:}")"; done
  cat <<'YAML'
  gate-ok:   # the ONE required check for the whole repo (a bare `gate-ok`, no prefix)
YAML
  printf '    needs: [%s]\n' "$needs"
  cat <<'YAML'
    if: always()
    runs-on: ubuntu-latest
    steps:
      - name: Require every gate job to have passed
        env:
          RESULTS: ${{ toJSON(needs) }}
        run: |
          set -euo pipefail
          # Iterate over the needs context itself: a package added above is checked
          # automatically, so one can never silently escape the gate. A skipped
          # (path-filtered) package is fine; only failure/cancelled blocks the merge.
          bad="$(printf '%s' "$RESULTS" | jq -r 'to_entries[] | select(.value.result=="failure" or .value.result=="cancelled") | .key')"
          if [ -n "$bad" ]; then echo "::error::gate job(s) did not pass: $bad"; exit 1; fi
          echo "all gate jobs passed or were skipped"
YAML
}

gen_mono_gate() { # <pair...> - the whole monorepo gate.yml, to stdout
  local pair pkgs=""
  for pair in "$@"; do pkgs+="${pkgs:+ }${pair#*:}"; done
  cat <<YAML
name: gate
on: { pull_request: {}, push: { branches: [main] } }
concurrency:
  group: gate-\${{ github.ref }}
  cancel-in-progress: true
permissions:
  contents: read
jobs:
  changes:
    uses: $REPO/.github/workflows/changes.yml@$REF
    with:
      packages: "$pkgs"
      ignore_globs: |
        *.md
        docs/**
        */.habit-hooks/snooze.json
YAML
  for pair in "$@"; do gen_mono_gate_pkg "${pair%%:*}" "${pair#*:}"; done
  gen_mono_gate_ok "$@"
}

gen_mono_bootstrap() { # <pair...> - one bootstrap job per package, to stdout
  local pair stack dir jobid
  cat <<'YAML'
name: bootstrap
on:
  workflow_dispatch: {}
  schedule:
    - cron: '0 6 * * *'   # daily auto-prune - each package opens at most one PR/day
jobs:
YAML
  for pair in "$@"; do
    stack="${pair%%:*}"; dir="${pair#*:}"; resolve_stack "$stack"
    jobid="$(mono_jobid "$dir")"
    cat <<YAML
  $jobid:
    uses: $REPO/.github/workflows/bootstrap.yml@$REF
    with:
      working_directory: "$dir"
      habit_hooks_plugin: "$R_PLUGIN"
    permissions: { contents: write, pull-requests: write }
YAML
  done
}

validate_mono_pairs() { # <pair...> - each arg must be <facade-stack>:<subdir>
  local pair stack dir
  for pair in "$@"; do
    case "$pair" in *:*) : ;; *) echo "mono arg must be stack:dir, got '$pair'" >&2; exit 2 ;; esac
    stack="${pair%%:*}"; dir="${pair#*:}"
    case "$stack" in
      ts|java|php|dotnet) : ;;
      kotlin) echo "--mono does not support 'kotlin' (no reusable gate yet); use ts|java|php|dotnet" >&2; exit 2 ;;
      python) echo "--mono does not support 'python' yet (facade exists, mono wiring not generated); use ts|java|php|dotnet" >&2; exit 2 ;;
      *) echo "unknown stack '$stack' in '$pair'" >&2; exit 2 ;;
    esac
    if [ -z "$dir" ] || [ "$dir" = "." ]; then
      echo "mono package dir must be a non-root subdir, got '$dir'" >&2; exit 2
    fi
  done
}

print_next_steps() { # <gate_check_name> [mono_note]
  cat <<'NEXT'

== Next steps ==
1. Pin versions: set tool versions in mise.toml and, ideally, re-run with
   FOUNDRY_REF=<a tag or SHA> so the reusable workflows are pinned, not floating on main.
2. Install detectors + seed the smell baseline: run the `bootstrap` workflow once
   (Actions tab -> bootstrap -> Run workflow). It opens a PR with .habit-hooks/snooze.json.
   Some sensors ship DISABLED (opt-in) - skim .habit-hooks/config.toml for
   `[sensors.*] disabled = true` and enable the ones you can support.
3. Turn on Renovate (or Dependabot) so the pins stay fresh.
4. Branch protection on `main` (Settings -> Branches), require these two checks
   (names must match EXACTLY; enable "require branches up to date"):
NEXT
  printf '     - %-24s(the language gate + structural smells)\n' "$1"
  printf '     - %-24s(secret scan + ruleset-guard + SAST)\n' "security / security-ok"
  cat <<'NEXT'
   Do NOT require the `bootstrap` job.
5. Commit, open a PR, and confirm the gate is green from a clean tree.
NEXT
  if [ -n "${2:-}" ]; then printf '\n%s\n' "$2"; fi
}

# --- dispatch ---------------------------------------------------------------
if [ "${1:-}" = "--mono" ]; then
  shift
  [ "$#" -ge 1 ] || { echo "usage: foundry-init.sh --mono <stack:dir> [<stack:dir>...]" >&2; exit 2; }
  PAIRS=("$@")
  validate_mono_pairs "${PAIRS[@]}"
  echo "== Foundry monorepo scaffold ($# packages) @ $REF =="
  for pair in "${PAIRS[@]}"; do scaffold_package "${pair%%:*}" "${pair#*:}"; done
  repo_level_once
  echo "- caller workflows (pinned to $REF)"
  gen_mono_gate "${PAIRS[@]}" | write ".github/workflows/gate.yml"
  emit_security_and_ratchet
  gen_mono_bootstrap "${PAIRS[@]}" | write ".github/workflows/bootstrap.yml"
  MONO_NOTE="Monorepo: the required check is a bare \`gate-ok\` (a top-level job, so no
\`caller /\` prefix - unlike the single-stack \`gate / gate-ok\`). To change the package
set later, delete the generated .github/workflows/gate.yml + bootstrap.yml (they are
never clobbered) and re-run --mono with the full set of pairs."
  print_next_steps "gate-ok" "$MONO_NOTE"
else
  STACK="${1:?stack required: ts | java | php | kotlin | dotnet | python}"
  WD="${2:-.}"
  echo "== Foundry scaffold: $STACK @ $REF =="
  scaffold_package "$STACK" "$WD"   # sets R_CI / R_PLUGIN for the branches below
  repo_level_once
  echo "- caller workflows (pinned to $REF)"
  emit_single_gate "$STACK" "$WD"
  emit_security_and_ratchet
  if [ -n "$R_PLUGIN" ]; then emit_single_bootstrap "$R_PLUGIN" "$WD"; fi
  if [ -n "$R_CI" ]; then
    print_next_steps "gate / gate-ok"
  else
    # kotlin runs an inline top-level job named "Deterministic gate", so its
    # check context is that name, NOT `gate / gate-ok` (which needs a reusable call).
    print_next_steps "Deterministic gate"
  fi
fi
echo "Done."
