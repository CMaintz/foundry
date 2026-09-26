# Spec — Changed-scope gate (`FOUNDRY_SINCE`)

**Status:** In progress · **Owner:** CMaintz · **Date:** 2026-09-19
**Home:** foundry (per-`mise` template) · **Placement weight:** shift-left (local only)

**Implemented:** `mise/ts.toml` — `lint` + `test` honour `FOUNDRY_SINCE` (validated
across unset / valid-ref / empty / unresolvable-ref); `presets/agent/agent-loop.md` documents
the activation (fast scoped inner-loop runs, whole-tree final gate); `mise/java.toml` —
honest "Gradle already scopes it" note, `novar` folded into `lint` and made
ratchet-scoped via `FOUNDRY_BASE_REF`; reusable `java.yml` — separate `no-var` job +
`no_var` input removed, gate lint step passes `FOUNDRY_BASE_REF` (TOML/YAML/shell
validated). Pre-push hook and CI confirmed correctly whole-tree — unchanged.
**Remaining:** other-stack recipes (php/kotlin/dotnet/python). AutoApplicant inherits
the Java fold via its inline→foundry CI migration (separate work-stream).

## Problem

In-loop and pre-push both run the full gate over the *whole tree*. On a 300-word
edit the agent still pays for a whole-repo lint + the full test suite + a project-wide
type check. Slow feedback is the DX gap that remains once `/ship` and `/feature`
exist: fewer loop iterations per unit time, and a Stop hook that's slow enough to
tempt deferral to CI. The fix is not a different rule set — it's the *same* rules,
scoped to what changed, at the cheap placements only.

## Two "scopes" — do not conflate them

The instinct "quality checks should only look at changed files, everywhere" is right
for one meaning of scope and a **correctness bug** for the other. There are two:

- **Ratchet-scope — *which findings fail the build*.** Only *new* violations fail;
  legacy debt is accepted in a shrink-only baseline. This is safe and correct in
  **every placement including CI**, and foundry **already does it everywhere**:
  eslint-suppressions, `.habit-hooks/snooze.json`, Spotless `ratchetFrom origin/main`,
  Semgrep `--baseline-commit`, the no-`var` PMD rule (CI checks only changed files).
  So "point only at new work" — in the sense of *not failing on old debt* — is already
  the whole design.
- **Execute-scope — *which files the checker even runs over*.** Restricting the tool
  to the changed file set. Safe for **file-local** checks (a finding depends only on
  that one file); **wrong for whole-program** checks, because a changed file can break
  an *unchanged* one:
  - Change a function signature in `A`; caller `B` (untouched) no longer compiles.
    `tsc` run on `A` alone never sees it — type analysis is inherently whole-program.
  - Add an import that forms a cycle; detecting it needs the whole module graph.
  - Change a util; the test that exercises it lives in an unchanged file.

**So the rule is:** ratchet-scope always (fail only on new); execute-scope only for
file-local checks, and only at the fast placements — with **whole-tree CI as the
authoritative backstop** for whole-program checks. `FOUNDRY_SINCE` is the
execute-scope signal for the fast placements; it is *not* set in CI, precisely so a
cross-file break a scoped local run misses is caught one push later.

**Two scopes, two signals — don't reuse one for the other:**

- **`FOUNDRY_SINCE`** — the *execute-scope* speed signal. Set at the fast placements
  (in-loop, `/ship` pre-flight), **unset in CI**. Narrows which files a file-local verb
  runs over. Optional; unset ⇒ whole-tree.
- **`FOUNDRY_BASE_REF`** — the *ratchet-scope* base for diff-scoped rules that must fail
  only on *new* violations (e.g. Java `novar` folded into `lint`). Defaults to
  `origin/main`; **CI sets it to the PR base SHA** because `origin/main` isn't a reliable
  ref in a PR checkout. It is set *everywhere the rule runs, including CI* — that's the
  difference from `FOUNDRY_SINCE`. An unresolvable base ⇒ the rule skips (CI's
  full-history run is authoritative).

The two are orthogonal: a diff-scoped rule can honour `FOUNDRY_BASE_REF` (which commits
count as "new") while its host verb is also execute-scoped by `FOUNDRY_SINCE` (which
files to bother running). Conflating them — e.g. using `FOUNDRY_SINCE` as the ratchet
base — would make a rule pass in CI (where it's unset) that fails locally.

### Which checks are which — yes, this covers PMD, SpotBugs, everything

| Check | Kind | Execute-scope safe? | How foundry scopes it |
|---|---|---|---|
| Formatting (prettier, Spotless) | file-local | ✅ | Spotless `ratchetFrom`; prettier on changed |
| Single-file lint, no-`var` (PMD) | file-local | ✅ | changed-file list (CI already does no-`var`) |
| habit-hooks smells (PMD/phpmd/eslint/…) | file-local | ✅ | in-loop `--branch`; snooze ratchet |
| SpotBugs / Semgrep (SAST) | file-local *findings* | ✅ (filter findings to changed) | Semgrep `--baseline-commit`; SpotBugs report filtered to diff |
| Secret scan (gitleaks) | **history, not diff** | ❌ | full history by design — a secret 5 commits back isn't in the diff |
| Type-check (tsc, compileJava) | whole-program | ❌ | whole-tree; ratchet N/A |
| Tests | whole-program (cross-file deps) | ⚠️ dep-graph only | `vitest --changed` follows the import graph locally; whole-suite in CI |
| Architecture (ArchUnit, dep-cruiser) | whole-program (graph) | ❌ | whole-graph; FreezingArchRule/known-violations ratchet |

**PMD and SpotBugs specifically:** yes — PMD-backed smells are file-local and already
`--branch`-scoped in-loop and snooze-ratcheted; the no-`var` PMD rule is already
changed-file-scoped in CI. SpotBugs needs a full compile (so it can't cheaply
execute-scope), but its *findings* can and should be filtered to the changed set so it
only nags about new bugs. The taxonomy above is the general answer: **every checker
declares its kind, and scoping follows from the kind** — not an ad-hoc per-tool choice.

### Is this what CI does today?

For the **file-local** checks, yes — Spotless, no-`var`, Semgrep and habit-hooks are
all diff-scoped in CI already. For the **whole-program** checks (types, tests, and the
new arch rules) CI runs whole-tree **on purpose**, and should stay that way: that
whole-tree CI run is exactly the backstop that lets the fast local placements cut
corners safely. So "look at changed files and nothing else" is already true where it's
*safe*, and deliberately not true where it would miss cross-file breaks.

## Design

Introduce one scope signal: an environment variable **`FOUNDRY_SINCE=<git-ref>`**
(default when set but empty: merge-base with `origin/main`). Contract semantics:

- A verb **MAY** honour `FOUNDRY_SINCE` by restricting its work to files changed
  since that ref. A verb that cannot scope (e.g. project-wide type inference) simply
  ignores it and runs whole-tree — correctness is never traded for speed.
- A **caller MUST NOT require** it. Unset = whole-tree, the current behaviour. This
  keeps the "a caller never asks whether a verb exists / behaves specially" property.
- **CI never sets it.** Whole-tree CI stays the authoritative backstop, which is
  exactly what makes local scoping safe: a scoped local run can miss a cross-file
  break, and CI catches it one push later.

The in-loop Stop hook and the git pre-push hook set `FOUNDRY_SINCE` (to the
branch merge-base); `/ship` sets it for its fast pre-flight and unsets it for the
final authoritative `gate`. This is a **tier-(b) change** (verb *composition*,
repo-local) — no new contract verb, no change to the six verb names.

### Why an env var (not args or parallel tasks)

- **Trailing args** (`mise run test -- --since`) force every task to pass args
  through to a specific tool and leak tool syntax into callers.
- **Parallel tasks** (`test:changed`) double the task surface and make callers choose
  which to invoke — breaking the "verbs are uniform across repos" contract.
- **Env var** is invisible to any caller that doesn't set it, opt-in per verb, and
  costs zero contract growth. One signal, read where it helps, ignored where it can't.

## Per-stack wiring

### TypeScript (deep)
- `lint` → `eslint $(git diff --name-only --diff-filter=ACMR "$FOUNDRY_SINCE" -- '*.ts' '*.tsx')`
  when set; else current glob. (eslint-suppressions ratchet unaffected.)
- `test` → `vitest --changed "$FOUNDRY_SINCE"` (vitest's built-in changed-since).
- `typecheck` → **non-scopeable, documented.** `tsc` is project-global; `tsc-files`
  on changed files drops cross-file errors, so keep whole-tree. This is the honest
  asymmetry — typecheck stays full even in-loop; it's fast enough on MDB-sized repos.

### Java (deep)
- `lint` (Spotless) → **already changed-scoped** via `ratchetFrom origin/main`. No work.
- `typecheck` (`compileJava`) → Gradle incremental compilation already scopes this;
  `FOUNDRY_SINCE` is a no-op. Document it.
- `test` → Gradle has no native changed-file test selection. Wrapper computes changed
  test classes from the diff and runs `./gradlew :backend:test --tests <patterns>`;
  when the diff touches only non-test main classes, fall back to whole module (safe).
  **Honest note:** on the JVM the build dominates and Gradle's up-to-date checks
  already skip unaffected work, so the marginal win here is smaller than on TS. This
  spec does not pretend otherwise.

### Other stacks (recipe, 3–5 lines each)
- **PHP:** `phpstan analyse $(git diff …)`, `phpcs` on changed files; PHPUnit
  `--filter` by changed test classes.
- **Python:** ruff is fast enough whole-tree (leave it); `pytest --testmon` or `-k`
  for changed-scoped tests.
- **Kotlin/dotnet:** ktlint/dotnet-format on changed files; test filtering by
  changed test class — same shape as Java, same JVM/build caveat.

## Ratchet mechanics

None — this is not a baseline feature. The safety property is instead: **whole-tree
CI is unconditional**, so scoping can only ever make local runs *faster*, never
weaker. That invariant is the spec's load-bearing guarantee.

## ruleset-guard changes

None. No new watched files.

## Placement

| Placement | `FOUNDRY_SINCE` | Scope |
|---|---|---|
| In-loop (Stop hook) | set = merge-base | changeset only (fast) |
| Pre-push (`/ship` pre-flight) | set = merge-base | changeset; final `gate` unset = whole-tree |
| CI | **never set** | whole-tree (authoritative) |

## If-funded tier

N/A — pure local optimisation.

## Acceptance criteria

1. With `FOUNDRY_SINCE` set, `mise run lint`/`test` operate only on changed files;
   a timing measurement shows a scoped run materially faster than whole-tree on a
   one-file change.
2. With `FOUNDRY_SINCE` unset (CI), behaviour is byte-identical to today.
3. A deliberately induced cross-file type break is *missed* by a scoped local run but
   *caught* by whole-tree CI — proving the backstop and documenting the asymmetry.
4. Non-scopeable verbs (`typecheck` on TS, `compileJava`) are documented as such and
   run whole-tree regardless.

## Backport split

- **foundry:** the `FOUNDRY_SINCE` convention, the merge-base diff snippet, and the
  per-template wiring for each stack. A one-paragraph note in CONTRACT.md defining the
  MAY/MUST-NOT semantics.
- **consumer:** repo-specific test-selection quirks (e.g. AutoApplicant's
  changed-test-class mapping) if they exceed the shared snippet.
