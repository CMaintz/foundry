#!/usr/bin/env bash
# Smoke test for the javascript habit-hooks preset: build a throwaway plain-JS repo with
# the preset copied in, plant known smells in a source file and the same smells in a test
# file, run the real habit-sensors, and check the source smells are reported and the test
# files are not. A preset that silently checks nothing exits 0 everywhere else, so this is
# the only place that notices.
#   Usage: tests/habit-hooks-js-smoke.sh
#   Env:   HABIT_SENSORS  habit-sensors with the typescript + generic plugins (default: on PATH)
#          PRESET         preset basename under presets/habit-hooks (default: javascript)
#          PYTHON         interpreter for the JSON checks (default: python3, else python)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
HABIT_SENSORS="${HABIT_SENSORS:-habit-sensors}"
PRESET="${PRESET:-javascript}"
HH="$ROOT/presets/habit-hooks"

fail() { echo "FAIL: $*" >&2; exit 1; }

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
cat > package.json <<'EOF'
{
  "name": "smoke", "version": "0.0.0", "private": true, "type": "module",
  "main": "src/index.mjs",
  "scripts": { "test": "node --test" },
  "devDependencies": { "eslint": "10.12.0", "knip": "6.39.0", "jscpd": "5.4.0" }
}
EOF
npm install --no-audit --no-fund --silent

mkdir -p .habit-hooks src test
cp "$HH/$PRESET.toml" .habit-hooks/config.toml
cp "$HH/eslint.config.mjs" .habit-hooks/eslint.config.mjs
cp "$HH/javascript/knip.json" knip.json
cp "$HH/jscpd.json" .jscpd.json
# The repo has an eslint config of its own, the case where the plugin's built-in rules
# never run. The project's own rule must still be reported alongside the smells.
printf 'export default [{ rules: { "no-debugger": "error" } }];\n' > eslint.config.mjs

{ smelly used; echo "export const unusedExport = 1;"; echo "debugger;"; } > src/app.mjs
printf 'import { used } from "./app.mjs";\nconsole.log(used(1, 2, 3, 4));\n' > src/index.mjs
{
  echo 'import { used } from "../src/app.mjs";'
  echo 'import { fake } from "./fakes.mjs";'
  smelly copied
  echo "console.log(used, copied, fake);"
} > test/app.test.mjs
{ smelly fakeTotal; echo "export const fake = fakeTotal;"; } > test/fakes.mjs
git add -A

"$HABIT_SENSORS" --all --no-snooze > findings.json 2> sensors.err || { cat sensors.err; fail "habit-sensors exited non-zero"; }
if [ -s sensors.err ]; then cat sensors.err; fail "habit-sensors wrote to stderr"; fi

"$PYTHON" - findings.json <<'EOF' || { cat findings.json; exit 1; }
import json, sys
from collections import defaultdict

seen = defaultdict(set)
for finding in json.load(open(sys.argv[1])):
    for issue in finding["issues"]:
        path = issue["details"].get("file", issue["key"]).replace("\\", "/")
        seen[finding["smell"]].add(path)

errors = []
for smell in ("oversized-function", "too-many-parameters", "var-declaration",
              "non-const-binding", "loose-equality", "unused-export", "no-debugger"):
    if "src/app.mjs" not in seen[smell]:
        errors.append(f"{smell} not reported for src/app.mjs")
for smell, paths in seen.items():
    errors += [f"{smell} reported for test file {p}" for p in paths if p.startswith("test/")]
if seen["non-essential-comment"]:
    errors.append("non-essential-comment is reported; the preset disables it")
if errors:
    sys.exit("FAIL: " + "\n      ".join(errors))
EOF
echo "ok [$PRESET]: smells reported for src/app.mjs, none for test/"
