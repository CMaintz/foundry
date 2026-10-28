#!/usr/bin/env python3
"""Does a change to a ratchet baseline LOOSEN it? Exit 1 = loosening (needs the
ruleset-change label), 0 = safe.

Per-entry, not aggregate: any entry ADDED or INCREASED is a loosening; removals
are fine. This is what defeats the offset attack - fixing one violation while
suppressing another nets zero on a summed count, but shows up here as an added
entry.

Not vendored: foundry's reusable _guards.yml and ratchet-report.yml fetch this file
from foundry at their own pinned ref and run it against the caller's checkout.

Kinds:
  eslint  eslint-suppressions.json      (per file+rule count)
  snooze  habit-hooks snooze.json, and dependency-cruiser known-violations JSON
          (position-independent multiset of scalar leaves - an added violation
          increments its scalars, so it's caught; reorder/remove are safe)
  lines   ArchUnit FreezingArchRule store files (one frozen violation per line;
          run once per changed store file under archunit_store/)
  coverage  prompt-eval manifest.json - INVERSE: a REMOVED fixture is less coverage,
            so removal (not addition) is the loosening
  inline  IN-SOURCE suppression directives, test-skips and config demotions, counted
          tree-wide per (file, directive) at both refs - an added eslint-disable /
          @ts-ignore / @SuppressWarnings / # noqa / #pragma warning disable /
          coverage-exclusion / it.skip / editorconfig severity=none is a loosening the
          baseline files above never see. No <path>: the base tree IS the baseline. Same
          per-entry shrink-only property as eslint, so the offset attack is still caught.
  tests   TEST DELETION: uncommented test declarations summed over the PR's changed
          test files, INVERSE - fewer at head than base means a test was deleted or
          commented out with no replacement. A split, move or rename nets out. No <path>.

Usage: ruleset_guard.py <eslint|snooze|lines|coverage> <base-ref> <head-ref> <path>
       ruleset_guard.py <inline|tests|workflow-approve> <base-ref> <head-ref>
       ruleset_guard.py signoff <events.jsonl> <label,label> <head-time>
"""

import json
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime


def eslint_counts(d):
    """eslint-suppressions.json: {file: {rule: {count: N}}} -> Counter[(file,rule)] = N."""
    c = Counter()
    for f, rules in (d or {}).items():
        for rule, v in (rules or {}).items():
            c[(f, rule)] = (v or {}).get("count", 0)
    return c


def value_counts(x):
    """snooze.json: multiset of scalar leaf values, position-independent (reorder is safe)."""
    c = Counter()

    def walk(v):
        if isinstance(v, dict):
            for w in v.values():
                walk(w)
        elif isinstance(v, list):
            for w in v:
                walk(w)
        else:
            c[v] += 1

    walk(x)
    return c


def line_counts(text):
    """ArchUnit freeze store: one violation per line -> multiset of non-empty lines.

    Comment lines (starting with '#') are skipped: ArchUnit's default store index
    (`stored.rules`) is a Java Properties file, which writes a '#<timestamp>' comment
    that changes on every store update. Counting it would flag an added line on each
    legitimate prune. Real violation descriptions never start with '#'.
    """
    c = Counter()
    for ln in (text or "").splitlines():
        ln = ln.strip()
        if ln and not ln.startswith("#"):
            c[ln] += 1
    return c


def coverage_counts(text):
    """prompt-eval manifest.json: multiset of the `fixtures` list (the coverage surface)."""
    d = json.loads(text) if text.strip() else {}
    c = Counter()
    for item in d.get("fixtures") or []:
        c[item] += 1
    return c


def loosened(kind, old_text, new_text):
    if kind == "lines":
        o, n = line_counts(old_text), line_counts(new_text)
        return [k for k in n if n[k] > o.get(k, 0)]
    if kind == "coverage":
        # INVERSE of a debt baseline: for a test-coverage surface, a REMOVED entry is
        # *less* coverage = a loosening. Adding entries is fine (tightening).
        o, n = coverage_counts(old_text), coverage_counts(new_text)
        return [k for k in o if n.get(k, 0) < o[k]]
    old = json.loads(old_text) if old_text.strip() else None
    new = json.loads(new_text) if new_text.strip() else None
    counts = eslint_counts if kind == "eslint" else value_counts
    o, n = counts(old), counts(new)
    return [k for k in n if n[k] > o.get(k, 0)]


def _git_show(ref, path):
    r = subprocess.run(["git", "show", f"{ref}:{path}"], capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else ""


# Never scan this script or its fixtures - they contain every directive by construction.
_EXCLUDE = [":(exclude)scripts/ruleset_guard.py", ":(exclude)tests/test_ruleset_guard.py"]
# Plain git pathspecs match from the repo root and their `*` crosses `/`, so a leading
# `*` (e.g. `*.ts`) matches at any depth. A pattern that must anchor on the file NAME
# (`test_*.py`) uses `:(glob)**/`: `**/` is any depth and `*` stops at `/`, so it neither
# misses `tests/test_x.py` nor matches `test_helpers/util.py`.
# Real source files.
CODE_PATHS = [
    "*.ts",
    "*.tsx",
    "*.js",
    "*.jsx",
    "*.mjs",
    "*.cjs",
    "*.py",
    "*.cs",
    "*.java",
    "*.kt",
    "*.kts",
    "*.php",
    *_EXCLUDE,
]
# Gate-defining config files. A config-only PR that demotes a rule (severity = none,
# "strict": false, <NoWarn>) never touches source_paths, so the bundled ruleset-guard
# below never fires on it - this always-run scan is the only thing that catches it.
CONFIG_PATHS = ["*.editorconfig", "*.csproj", "*.props", ":(glob)**/tsconfig*.json", *_EXCLUDE]
# Test files only. Test-SKIP directives (and the `tests` deletion count) are meaningful
# ONLY here - scanning all source for `.skip(`/`xit(` false-matches app code (a paging
# `.skip(`, `process.exit(` -> `xit(`), so those directives use this, not CODE_PATHS.
TEST_PATHS = [
    "*.test.ts",
    "*.test.tsx",
    "*.test.js",
    "*.test.jsx",
    "*.test.mjs",
    "*.test.cjs",
    "*.spec.ts",
    "*.spec.tsx",
    "*.spec.js",
    "*.spec.jsx",
    "*.spec.mjs",
    "*.spec.cjs",
    ":(glob)**/test_*.py",
    "*_test.py",
    "*Test.java",
    "*Tests.java",
    "*IT.java",
    "*Test.kt",
    "*Tests.kt",
    "*Test.cs",
    "*Tests.cs",
    "*Test.php",
    *_EXCLUDE,
]

# In-source suppressions / test-skips / config demotions, each (name, regex, pathspec).
# The regexes are BUILT FROM FRAGMENTS so this file never contains a directive literally
# (else the scan would flag its own source). Extended-regex (git grep -E); one hit per
# line, so the count is per-(file, directive) line-hits - stable at both refs, which is
# all the shrink-only comparison needs. Only LOOSENING values are listed, so a demotion
# is an added entry (flagged) and a re-promotion is a removal (safe) for free.
INLINE_DIRECTIVES = [
    ("eslint-disable", "eslint-" + "disable", CODE_PATHS),
    # Inline rule config (`/* eslint no-console: "off" */`): `eslint` then a space, so
    # `eslint-disable` / `eslint-env` stay out; the colon is what makes it rule config.
    ("eslint-inline-config", r"/\* *es" + "lint +[^*]*:", CODE_PATHS),
    ("ts-ignore", "@ts-" + "ignore", CODE_PATHS),
    ("ts-expect-error", "@ts-" + "expect-error", CODE_PATHS),
    ("ts-nocheck", "@ts-" + "nocheck", CODE_PATHS),
    ("istanbul-ignore", "istanbul " + "ignore", CODE_PATHS),
    ("c8-ignore", "c8 " + "ignore", CODE_PATHS),
    ("noqa", "# *no" + "qa", CODE_PATHS),
    ("py-type-ignore", "# *type: *" + "ignore", CODE_PATHS),
    ("pylint-disable", "pylint: *" + "disable", CODE_PATHS),
    ("py-no-cover", "pragma: *no " + "cover", CODE_PATHS),
    ("java-suppresswarnings", "@Suppress" + "Warnings", CODE_PATHS),
    ("java-suppressfbwarnings", "@Suppress" + "FBWarnings", CODE_PATHS),
    ("java-nopmd", "NO" + "PMD", CODE_PATHS),
    ("kotlin-suppress", "@Suppress" + r"\(", CODE_PATHS),
    ("kotlin-file-suppress", "@file: *" + "Suppress", CODE_PATHS),
    ("csharp-pragma-warning", "pragma warning " + "disable", CODE_PATHS),
    ("csharp-suppressmessage", r"\[" + "SuppressMessage", CODE_PATHS),
    ("csharp-exclude-coverage", "ExcludeFrom" + "CodeCoverage", CODE_PATHS),
    ("php-phpstan-ignore", "@phpstan-" + "ignore", CODE_PATHS),
    ("php-psalm-suppress", "@psalm-" + "suppress", CODE_PATHS),
    ("phpcs-ignore", "phpcs: *" + "(ignore|disable)", CODE_PATHS),
    ("php-coverage-ignore", "@codeCoverage" + "Ignore", CODE_PATHS),
    # Foundry's own PMD --suppress-marker values (habit-hooks smells, no-var).
    ("foundry-allow", "foundry-allow-" + "(smell|var)", CODE_PATHS),
    # Test-skips: a skipped/narrowed test is a quietly disabled check. Scoped to TEST_PATHS
    # (a skip is only a skip in a test file), and js-xit is anchored with `(^|[^A-Za-z])` so
    # it does not match `exit(` / `fixit(`. Deleting a test outright is NOT caught here - the
    # `tests` kind and a coverage floor are the backstop.
    ("js-skip", r"\.skip" + r"\(", TEST_PATHS),
    ("js-only", r"\.only" + r"\(", TEST_PATHS),
    ("js-xit", "(^|[^A-Za-z])x(it|describe) *" + r"\(", TEST_PATHS),
    ("py-skip", "@(pytest.mark|unittest).*" + "skip", TEST_PATHS),
    ("py-xfail", r"pytest\.(mark\.)?" + "xfail", TEST_PATHS),
    ("py-pytestmark-skip", "pytestmark *=.*" + "skip", TEST_PATHS),
    ("junit-disabled", "@(Disabled|" + "Ignore)", TEST_PATHS),
    ("xunit-skip", r"\(Skip *=", TEST_PATHS),
    ("dotnet-ignore", r"\[" + "Ignore", TEST_PATHS),
    ("phpunit-skip", "markTest" + "(Skipped|Incomplete)", TEST_PATHS),
    # Config demotions: flipping a rule off in a config file is the same gaming move as an
    # inline disable, and a config-only PR dodges the bundled guard.
    ("editorconfig-demote", "severity *= *(none|silent|" + "suggestion)", CONFIG_PATHS),
    ("tsconfig-unstrict", '"strict[A-Za-z]*" *: *' + "false", CONFIG_PATHS),
    ("csproj-nowarn", "<No" + "Warn>", CONFIG_PATHS),
]


# Workflow lines that let a job approve PRs. Actions approving PRs is intentional (Renovate,
# baseline prune), so only GROWTH is flagged, per (file, directive) like the inline kind:
# a Renovate SHA bump rewrites a line in place and keeps the count. `^[^#]*` skips YAML
# comments (usage examples in workflow headers). A job token's approve power comes from
# `pull-requests: write` (or write-all); the rest are the ways a step uses it.
WORKFLOW_PATHS = [".github/workflows/*.yml", ".github/workflows/*.yaml"]
WORKFLOW_DIRECTIVES = [
    ("workflow-pr-write", "^[^#]*(pull-requests: *write|write-" + "all)", WORKFLOW_PATHS),
    ("workflow-approve-cli", "^[^#]*gh +pr +review.*(--approve|-a( |$))", WORKFLOW_PATHS),
    ("workflow-approve-event", "^[^#]*event[\"']? *[:=] *[\"']?" + "APPROVE", WORKFLOW_PATHS),
    ("workflow-approve-action", "^[^#]*(auto-approve|approve-pull-request)", WORKFLOW_PATHS),
]


def inline_counts(ref, directives=INLINE_DIRECTIVES):
    """Counter[(file, directive)] of hits for each (name, regex, pathspec) at a ref."""
    c = Counter()
    for name, pat, paths in directives:
        r = subprocess.run(
            ["git", "grep", "-I", "-E", "-e", pat, ref, "--", *paths],
            capture_output=True,
            text=True,
        )
        # git grep: 0 = matches, 1 = no matches (both fine), >1 = real error.
        if r.returncode > 1:
            raise SystemExit(f"ruleset_guard inline: git grep failed for {name}: {r.stderr.strip()}")
        for line in r.stdout.splitlines():
            # "<ref>:<path>:<text>" - a ref holds no colon, so field 1 is the path.
            parts = line.split(":", 2)
            if len(parts) >= 2:
                c[(parts[1], name)] += 1
    return c


def inline_loosened(base, head, directives=INLINE_DIRECTIVES):
    o, n = inline_counts(base, directives), inline_counts(head, directives)
    return [k for k in n if n[k] > o.get(k, 0)]


# Test-declaration markers, matched per line in test files (TEST_PATHS above). Built from
# fragments for the same self-match reason as INLINE_DIRECTIVES. `(^|[^A-Za-z])` keeps
# `it`/`test` from matching inside `unit(`/`fixit(`; the trailing `([^A-Za-z]|$)` keeps
# `@TestConfiguration` and `[TestFixture]` out. `describe(` is left out on purpose:
# commenting out a describe also comments its `it(` lines, and counting it would make
# removing a wrapper look like a deleted test.
TEST_DEFS = [
    "(^|[^A-Za-z])(it|test)[.(]",
    "def " + "test",
    "function " + "test",
    "@" + "Test([^A-Za-z]|$)",
    r"\[" + "(Fact|Theory|Test|TestMethod|DataTestMethod|TestCase)([^A-Za-z]|$)",
]
_TEST_DEF_RE = re.compile("|".join(TEST_DEFS))


def count_test_defs(text):
    """Test-declaration lines in a file's text, skipping commented-out ones.

    A line comment is a line starting with `//`, `*` or `#` (but not PHP's `#[` attribute).
    A block comment counts only when `/*` opens the line: a mid-line `/*` is as likely a
    glob string (`'src/**/*.ts'`) as a comment, and treating it as one would hide every
    test after it.
    """
    n, in_block = 0, False
    for line in text.splitlines():
        s = line.strip()
        if in_block:
            in_block = "*/" not in s
            continue
        if s.startswith("/*"):
            in_block = "*/" not in s[2:]
            continue
        if s.startswith(("//", "*")) or (s.startswith("#") and not s.startswith("#[")):
            continue
        if _TEST_DEF_RE.search(line):
            n += 1
    return n


def _git_lines(*args):
    r = subprocess.run(["git", *args], capture_output=True, text=True)
    # git grep exits 1 for "no matches"; anything else above 0 is a real error.
    if r.returncode > (1 if args[0] == "grep" else 0):
        raise SystemExit(f"ruleset_guard tests: git {args[0]} failed: {r.stderr.strip()}")
    return [ln for ln in r.stdout.splitlines() if ln]


def _e(patterns):
    return [a for p in patterns for a in ("-e", p)]


def test_counts(ref, paths=None):
    """Counter[file] = uncommented test declarations at a git ref, over `paths` (default:
    every test file). A path absent at the ref counts 0."""
    if paths is None:
        # Only files with a candidate line can count above 0; "<ref>:<path>" per line.
        hits = _git_lines("grep", "-I", "-l", "-E", *_e(TEST_DEFS), ref, "--", *TEST_PATHS)
        paths = [ln.split(":", 1)[1] for ln in hits]
    return Counter({p: count_test_defs(_git_show(ref, p)) for p in paths})


def tests_loosened(base, head):
    """Test files that lost declarations, reported only when the PR's test files hold
    fewer declarations in total than at base. Summed across every changed test file (both
    sides of a rename: --no-renames), so a split, move or rename nets out while a test
    deleted or commented out without a replacement does not."""
    changed = _git_lines("diff", "--name-only", "--no-renames", base, head, "--", *TEST_PATHS)
    o, n = test_counts(base, changed), test_counts(head, changed)
    if sum(n.values()) >= sum(o.values()):
        return []
    # On a split that also drops a test, the decreased file is the old one, so show the
    # net and every changed file's counts for a human to find where it went.
    net = f"net {sum(o.values())} -> {sum(n.values())} test declarations across changed test files"
    return [net, *(f"{f} ({o[f]} -> {n[f]})" for f in changed)]


def _instant(ts):
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def signoff(events, labels, head_time):
    """(valid, stale): which of `labels` (on the PR now) still sign it off.

    A sign-off label counts only if its most recent `labeled` event is later than
    `head_time` (when the head commit was pushed), so a push after the human reviewed voids
    the label. `events` are the PR's issue events as {event, name, created_at}.
    """
    head = _instant(head_time)
    last = {}
    for e in events:
        if e.get("event") == "labeled" and e.get("name") in labels:
            at = _instant(e["created_at"])
            last[e["name"]] = max(at, last.get(e["name"], at))
    valid = [lb for lb in labels if lb in last and last[lb] > head]
    return valid, [lb for lb in labels if lb not in valid]


_KINDS = {"eslint", "snooze", "lines", "coverage", "inline", "inline-count", "tests", "tests-count", "workflow-approve", "signoff"}

if __name__ == "__main__":
    kind = sys.argv[1] if len(sys.argv) > 1 else ""
    if kind not in _KINDS:
        sys.exit(
            f"ruleset_guard: unknown kind {kind!r}. The calling workflow and this "
            f"script are out of step - pin the workflow to a foundry ref whose "
            f"scripts/ruleset_guard.py knows this kind."
        )
    if kind == "signoff":
        # signoff <events.jsonl> <label,label> <head-time>: prints the labels that still
        # sign the PR off, one per line; exit 1 when none does.
        with open(sys.argv[2], encoding="utf-8") as fh:
            events = [json.loads(ln) for ln in fh if ln.strip()]
        present = [lb for lb in sys.argv[3].split(",") if lb]
        valid, stale = signoff(events, present, sys.argv[4])
        for lb in valid:
            print(lb)
        for lb in stale:
            print(f"  {lb}: applied before the head commit was pushed (or never) - re-apply it", file=sys.stderr)
        sys.exit(0 if valid else 1)
    if kind in ("inline-count", "tests-count"):
        # Tree-wide total at one ref, for the ratchet report.
        counts = inline_counts if kind == "inline-count" else test_counts
        print(sum(counts(sys.argv[2]).values()))
        sys.exit(0)
    if kind in ("inline", "tests", "workflow-approve"):
        base, head = sys.argv[2:4]
        if kind == "tests":
            bad = tests_loosened(base, head)
        else:
            bad = inline_loosened(base, head, WORKFLOW_DIRECTIVES if kind == "workflow-approve" else INLINE_DIRECTIVES)
    else:
        base, head, path = sys.argv[2:5]
        bad = loosened(kind, _git_show(base, path), _git_show(head, path))
    verb = {"coverage": "removed/decreased", "tests": "tests"}.get(kind, "added/increased")
    for k in bad[:20]:
        print(f"  {verb}: {k}", file=sys.stderr)
    sys.exit(1 if bad else 0)
