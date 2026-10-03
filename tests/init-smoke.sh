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
    bash "$ROOT/scripts/foundry-init.sh" "$stack" > first.log 2>&1 || { cat first.log; fail "init exited non-zero"; }

    expected=(mise.toml .habit-hooks/config.toml .gitleaks.toml renovate.json
      scripts/ruleset_guard.py scripts/foundry-verb-wrap scripts/foundry-loop-report
      .github/workflows/gate.yml .github/workflows/security.yml .github/workflows/ratchet.yml)
    case "$stack" in
      ts) expected+=(tsconfig.json scripts/npm-audit-ratchet.mjs .github/workflows/bootstrap.yml) ;;
      java) expected+=(pmd/ruleset.xml config/pmd/no-var.xml .jscpd.json .github/workflows/bootstrap.yml) ;;
      php | dotnet) expected+=(.github/workflows/bootstrap.yml) ;;
    esac
    for f in "${expected[@]}"; do [ -s "$f" ] || fail "missing or empty: $f"; done
    [ -x scripts/foundry-verb-wrap ] || fail "foundry-verb-wrap is not executable"
    grep -qxF '.foundry/' .gitignore || fail ".gitignore lacks .foundry/"
    grep -q '@v0.0.0-smoke' .github/workflows/security.yml || fail "workflows not pinned to FOUNDRY_REF"

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
