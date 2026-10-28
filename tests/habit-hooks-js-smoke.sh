#!/usr/bin/env bash
# Smoke test for the javascript and typescript habit-hooks presets: build a throwaway repo
# in the preset's language with the preset copied in, plant known smells in a source file
# and the same smells in a test file, run the real habit-sensors, and check the source
# smells are reported and the test files are not. A preset that silently checks nothing
# exits 0 everywhere else, so this is the only place that notices.
#   Usage: tests/habit-hooks-js-smoke.sh
#   Env:   HABIT_SENSORS  habit-sensors with the typescript + generic plugins (default: on PATH)
#          PRESET         javascript or typescript (default: javascript)
#          PYTHON         interpreter for the JSON checks (default: python3, else python)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HABIT_SENSORS="${HABIT_SENSORS:-habit-sensors}"
PRESET="${PRESET:-javascript}"
HH="$ROOT/presets/habit-hooks"

fail() { echo "FAIL: $*" >&2; exit 1; }

# Each repo has an eslint config of its own, the case where the plugin's built-in rules
# never run; its own no-debugger rule must still be reported alongside the smells. The TS
# repo's is the usual typescript-eslint config, which is what parses its .ts files.
case "$PRESET" in
  javascript)
    EXT=mjs
    DEPS='"eslint": "10.12.0", "knip": "6.39.0", "jscpd": "5.4.0"'
    ESLINT_CONFIG='export default [{ rules: { "no-debugger": "error" } }];' ;;
  typescript)
    EXT=ts
    DEPS='"eslint": "10.12.0", "knip": "6.39.0", "jscpd": "5.4.0", "ts-morph": "28.0.0",
    "typescript": "6.0.3", "typescript-eslint": "8.72.1"'
    ESLINT_CONFIG='import tseslint from "typescript-eslint";
export default [...tseslint.configs.recommended, { rules: { "no-debugger": "error" } }];' ;;
  *) fail "PRESET must be javascript or typescript, not $PRESET" ;;
esac

# One function over every structural limit the preset sets: 13 lines, 4 params, a `var`,
# a `let` never reassigned and a loose `==`. Its body is also long enough for jscpd to
# call the copy in the test file a duplicate.
smelly() {
  cat <<EOF
export function $1(a, b, c, d) {
  var total = 0;
  let unchanged = 2;
  if (a == b) total += 1;
  total += c;
  total += d;
  total += a * 2;
  total += b * 3;
  total += c * 4;
  total += d * 5;
  total += unchanged;
  return total;
}
EOF
}

dir="$(mktemp -d)"
trap 'rm -rf "$dir"' EXIT
cd "$dir"
git init -q
printf 'node_modules/\n' > .gitignore
# Probed by running it, from here: on Windows `python3` can be the Store stub or a mise
# shim with no python configured for this directory, both on PATH and both failing.
if [ -z "${PYTHON:-}" ]; then
  if python3 -c '' > /dev/null 2>&1; then PYTHON=python3; else PYTHON=python; fi
fi
cat > package.json <<EOF
{
  "name": "smoke", "version": "0.0.0", "private": true, "type": "module",
  "main": "src/index.$EXT",
  "scripts": { "test": "node --test" },
  "devDependencies": { $DEPS }
}
EOF
npm install --no-audit --no-fund --silent

mkdir -p .habit-hooks src test
cp "$HH/$PRESET.toml" .habit-hooks/config.toml
cp "$HH/eslint.config.mjs" .habit-hooks/eslint.config.mjs
# The TS repo keeps the plugin's own knip config, which already looks at src/**/*.ts.
if [ "$PRESET" = javascript ]; then cp "$HH/javascript/knip.json" knip.json; fi
cp "$HH/jscpd.json" .jscpd.json
printf '%s\n' "$ESLINT_CONFIG" > eslint.config.mjs

{ smelly used; echo "export const unusedExport = 1;"; echo "debugger;"; } > "src/app.$EXT"
printf 'import { used } from "./app.%s";\nconsole.log(used(1, 2, 3, 4));\n' "$EXT" > "src/index.$EXT"
{
  echo "import { used } from \"../src/app.$EXT\";"
  smelly copied
  echo "console.log(used, copied);"
} > "test/app.test.$EXT"
# Only the JS preset excludes test dirs, for node --test's unsuffixed fakes and fixtures.
if [ "$PRESET" = javascript ]; then
  { smelly fakeTotal; echo "export const fake = fakeTotal;"; } > test/fakes.mjs
fi
git add -A

"$HABIT_SENSORS" --all --no-snooze > findings.json 2> sensors.err || { cat sensors.err; fail "habit-sensors exited non-zero"; }
if [ -s sensors.err ]; then cat sensors.err; fail "habit-sensors wrote to stderr"; fi

"$PYTHON" - findings.json "src/app.$EXT" <<'EOF' || { cat findings.json; exit 1; }
import json, sys
from collections import defaultdict

seen = defaultdict(set)
for finding in json.load(open(sys.argv[1])):
    for issue in finding["issues"]:
        path = issue["details"].get("file", issue["key"]).replace("\\", "/")
        seen[finding["smell"]].add(path)

source = sys.argv[2]
errors = []
for smell in ("oversized-function", "too-many-parameters", "var-declaration",
              "non-const-binding", "loose-equality", "unused-export", "no-debugger"):
    if source not in seen[smell]:
        errors.append(f"{smell} not reported for {source}")
for smell, paths in seen.items():
    errors += [f"{smell} reported for test file {p}" for p in paths if p.startswith("test/")]
if seen["non-essential-comment"]:
    errors.append("non-essential-comment is reported; the preset disables it")
if errors:
    sys.exit("FAIL: " + "\n      ".join(errors))
EOF
echo "ok [$PRESET]: smells reported for src/app.$EXT, none for test/"
