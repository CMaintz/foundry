#!/usr/bin/env bash
# Smoke test for scripts/foundry-init.sh: scaffold a throwaway repo per stack from THIS
# checkout (FOUNDRY_RAW=file://), then check the expected files exist and parse, the
# generated workflows pass actionlint, and a second run changes nothing.
#   Usage: tests/init-smoke.sh [stack...]    (default: every stack)
#   Env:   ACTIONLINT  path to actionlint (default: on PATH; skipped if absent)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ACTIONLINT="${ACTIONLINT:-actionlint}"
STACKS=("$@")
[ ${#STACKS[@]} -gt 0 ] || STACKS=(ts java php kotlin dotnet python)
# Point the scaffolder at THIS checkout. Exported once at top level so every per-test
# subshell inherits it (a per-subshell export would trip shellcheck SC2030/SC2031).
export FOUNDRY_RAW="file://$ROOT" FOUNDRY_REF="v0.0.0-smoke"

fail() { echo "FAIL [$stack]: $*" >&2; exit 1; }

snapshot() { find . -path ./.git -prune -o -type f ! -name '*.log' -print0 | sort -z | xargs -0 sha256sum; }

for stack in "${STACKS[@]}"; do
  dir="$(mktemp -d)"
  (
    cd "$dir"
    git init -q
    # A TS repo onboarding already has a package.json; seed one so init can inject the
    # structural-smell sensor devDeps (knip/ts-morph/jscpd) into it.
    if [ "$stack" = ts ]; then printf '{"name":"smoke","version":"0.0.0","private":true}\n' > package.json; fi
    bash "$ROOT/scripts/foundry-init.sh" "$stack" > first.log 2>&1 || { cat first.log; fail "init exited non-zero"; }

    expected=(mise.toml .habit-hooks/config.toml .gitleaks.toml renovate.json
      scripts/ruleset_guard.py scripts/foundry-verb-wrap scripts/foundry-loop-report
      .github/workflows/gate.yml .github/workflows/security.yml .github/workflows/ratchet.yml)
    case "$stack" in
      ts) expected+=(tsconfig.json .jscpd.json scripts/npm-audit-ratchet.mjs .github/workflows/bootstrap.yml) ;;
      java) expected+=(pmd/ruleset.xml config/pmd/no-var.xml .jscpd.json .github/workflows/bootstrap.yml) ;;
      dotnet) expected+=(Directory.Build.props .editorconfig .github/workflows/bootstrap.yml) ;;
      php) expected+=(.github/workflows/bootstrap.yml) ;;
      python) expected+=(ruff.toml .github/workflows/bootstrap.yml) ;;
    esac
    for f in "${expected[@]}"; do [ -s "$f" ] || fail "missing or empty: $f"; done
    if [ "$stack" = ts ]; then
      for d in knip ts-morph jscpd; do
        grep -q "\"$d\"" package.json || fail "package.json missing structural-smell devDep: $d"
      done
    fi
    [ -x scripts/foundry-verb-wrap ] || fail "foundry-verb-wrap is not executable"
    grep -qxF '.foundry/' .gitignore || fail ".gitignore lacks .foundry/"
    if [ "$stack" = python ]; then
      grep -qxF '.venv/' .gitignore || fail ".gitignore lacks .venv/"
      python3 -c 'import tomllib; tomllib.load(open("ruff.toml", "rb"))' || fail "ruff.toml does not parse"
    fi
    grep -q '@v0.0.0-smoke' .github/workflows/security.yml || fail "workflows not pinned to FOUNDRY_REF"

    # Facade stacks get a gate.yml that pins the gate.yml facade + passes `stack`; only
    # kotlin (no reusable workflow yet) gets the inline `mise run gate`.
    case "$stack" in
      kotlin) grep -q 'mise run gate' .github/workflows/gate.yml || fail "kotlin gate.yml is not the inline gate" ;;
      *) grep -q 'workflows/gate.yml@v0.0.0-smoke' .github/workflows/gate.yml || fail "$stack gate.yml does not pin the facade"
         grep -q "stack: \"$stack\"" .github/workflows/gate.yml || fail "$stack gate.yml does not pass stack: $stack" ;;
    esac

    python3 - <<'PY' || fail "a generated config does not parse"
import json, tomllib
for f in ("mise.toml", ".habit-hooks/config.toml", ".gitleaks.toml"):
    tomllib.load(open(f, "rb"))
json.load(open("renovate.json"))
PY

    if command -v "$ACTIONLINT" > /dev/null 2>&1; then
      "$ACTIONLINT" -shellcheck= .github/workflows/*.yml || fail "generated workflows fail actionlint"
    fi

    before="$(snapshot)"
    bash "$ROOT/scripts/foundry-init.sh" "$stack" > second.log 2>&1 || { cat second.log; fail "re-run exited non-zero"; }
    grep -q '  wrote:' second.log && fail "re-run wrote a file (must never clobber)"
    [ "$before" = "$(snapshot)" ] || fail "re-run changed the tree"
    echo "ok [$stack]"
  )
  rm -rf "$dir"
done

# Python with its own ruff config: a ruff.toml would override pyproject's [tool.ruff], so
# init must not place the preset.
if [[ " ${STACKS[*]} " == *" python "* ]]; then
  dir="$(mktemp -d)"
  (
    cd "$dir"
    git init -q
    printf '[tool.ruff]\nline-length = 100\n' > pyproject.toml
    bash "$ROOT/scripts/foundry-init.sh" python > init.log 2>&1 || { cat init.log; fail "init exited non-zero"; }
    [ ! -e ruff.toml ] || fail "ruff.toml placed although pyproject.toml configures ruff"
    echo "ok [python, own ruff config]"
  )
  rm -rf "$dir"
fi

# Monorepo: scaffold two packages into one repo; assert per-package assets land, the
# generated gate.yml wires both packages + the classifier + a bare gate-ok, and a
# re-run changes nothing.
stack="mono"
dir="$(mktemp -d)"
(
  cd "$dir"
  git init -q
  bash "$ROOT/scripts/foundry-init.sh" --mono java:backend ts:frontend > first.log 2>&1 \
    || { cat first.log; fail "mono init exited non-zero"; }

  expected=(backend/mise.toml frontend/mise.toml backend/.habit-hooks/config.toml
    frontend/.habit-hooks/config.toml backend/pmd/ruleset.xml frontend/tsconfig.json
    .gitleaks.toml renovate.json scripts/ruleset_guard.py
    .github/workflows/gate.yml .github/workflows/security.yml
    .github/workflows/ratchet.yml .github/workflows/bootstrap.yml)
  for f in "${expected[@]}"; do [ -s "$f" ] || fail "missing or empty: $f"; done

  g=.github/workflows/gate.yml
  for needle in 'changes.yml@v0.0.0-smoke' 'working_directory: backend' \
    'working_directory: frontend' "contains(fromJSON(needs.changes.outputs.changes), 'backend')" \
    'gate-ok:' 'toJSON(needs)'; do
    grep -qF "$needle" "$g" || fail "mono gate.yml missing: $needle"
  done

  python3 - <<'PY' || fail "a generated mono config does not parse"
import tomllib
for f in ("backend/mise.toml", "frontend/mise.toml", "backend/.habit-hooks/config.toml"):
    tomllib.load(open(f, "rb"))
PY

  if command -v "$ACTIONLINT" > /dev/null 2>&1; then
    "$ACTIONLINT" -shellcheck= .github/workflows/*.yml || fail "mono workflows fail actionlint"
  fi

  before="$(snapshot)"
  bash "$ROOT/scripts/foundry-init.sh" --mono java:backend ts:frontend > second.log 2>&1 \
    || { cat second.log; fail "mono re-run exited non-zero"; }
  grep -q '  wrote:' second.log && fail "mono re-run wrote a file (must never clobber)"
  [ "$before" = "$(snapshot)" ] || fail "mono re-run changed the tree"
  echo "ok [mono]"
)
rm -rf "$dir"
