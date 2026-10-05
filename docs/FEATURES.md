# FEATURES - the canonical inventory

**Purpose.** One place listing everything Foundry provides, so that when a feature
is built or improved *inside a consumer repo* (e.g. AutoApplicant), it's obvious
what should come back here. If a capability isn't in this list, it either doesn't
exist yet or it hasn't been backported - both are actionable.

## Backport discipline

**Every change that is not language-specific gets backported to foundry (or the
shared preset) the same day it's proven in a consumer repo.** Language-specific
details (a Spring version override, an app's Docker publish) stay in the consumer.
Everything else - a workflow pattern, a guard fix, a feedback improvement, a hook,
a preset tweak - is Foundry's and belongs here. When in doubt, backport: the cost
of a duplicated line in foundry is far less than the cost of drift.

Rule of thumb for "is it language-specific?": would a Kotlin repo and a React repo
both want it? If yes → foundry. If it names a single language's tool *as the
mechanism* (not just an example) → a per-language file (`mise/<lang>.toml`,
`presets/habit-hooks/<lang>.toml`), still in foundry.

## Reusable workflows (`.github/workflows/`)

**Public facades** (the CI API - pin these; they dispatch to the internals and expose one stable `*-ok` check each):

| Facade | Purpose |
|---|---|
| `gate.yml` | Dispatches by `stack` (ts/java/php/dotnet/python) to the per-stack language gate - the six verbs decomposed one-per-step + a structural-smells job (per-smell "what it means / fix toward" legend). Java adds an opt-in `spotbugs` job (no-`var` is folded into `lint`). |
| `security.yml` | Language-agnostic: secret scan (gitleaks) + `ruleset-guard` + diff-aware SAST (semgrep). |

**Internal reusables** (`_`-prefixed - implementation the facades call via nested local `uses:`; not the API): `_ts.yml` · `_java.yml` · `_php.yml` · `_dotnet.yml` · `_python.yml` (per-stack gates) · `_guards.yml` (secrets + ruleset-guard) · `_semgrep.yml` (SAST).

**Auxiliary reusables** (called directly, not behind a facade):

| Workflow | Purpose |
|---|---|
| `web.yml` | Max-file-length gate for HTML/CSS. |
| `bootstrap.yml` | Regenerate the habit-hooks snooze baseline on Linux (`--prune` to shrink), open a PR. |
| `ratchet-report.yml` | PR comment showing how the accepted-debt baselines moved. |
| `autofix.yml` | Label a PR `autofix` → runs `mise run fix`, commits + pushes the result. |
| `changes.yml` | Monorepo path classifier: given `packages` + `ignore_globs`, emits a JSON array of the packages a PR touched. Fail-safe (an unclassified path rebuilds everything; non-PR events build everything). See [Monorepo](#monorepo-one-repo-many-stacks). |
| `lint-workflows.yml` | actionlint + shellcheck + typos over foundry's own repo (a trigger, not reusable). |

## Monorepo: one repo, many stacks

A single-stack repo is one `foundry-init <stack>` scaffold. A monorepo is `foundry-init --mono <stack>:<dir> ...` (e.g. `--mono java:backend ts:frontend`): it scaffolds each package and generates exactly the workflow below - the `gate.yml` facade called once per package (each with its own `stack` + `working_directory`), gated by the `changes.yml` path classifier so a package builds only when it changed, and wrapped in one aggregate `gate-ok`. The template is here so you can read what it emits or hand-assemble it if you prefer:

```yaml
name: gate
on: { pull_request: {} }
jobs:
  changes:
    uses: CMaintz/foundry/.github/workflows/changes.yml@v2
    with:
      packages: "backend frontend"
      ignore_globs: |
        *.md
        docs/**
        */.habit-hooks/snooze.json
  backend:
    needs: changes
    if: contains(fromJSON(needs.changes.outputs.changes), 'backend')
    uses: CMaintz/foundry/.github/workflows/gate.yml@v2
    with: { stack: java, working_directory: backend, spotbugs: true }
  frontend:
    needs: changes
    if: contains(fromJSON(needs.changes.outputs.changes), 'frontend')
    uses: CMaintz/foundry/.github/workflows/gate.yml@v2
    with: { stack: ts, working_directory: frontend }
  gate-ok:   # the ONE required check for the whole repo (a bare `gate-ok`, no prefix)
    needs: [changes, backend, frontend]
    if: always()
    runs-on: ubuntu-latest
    steps:
      - name: Require every gate job to have passed
        env:
          RESULTS: ${{ toJSON(needs) }}
        run: |
          set -euo pipefail
          # Iterate over the needs context itself, so adding a package can't slip the
          # gate - every job in needs is checked. Skipped (path-filtered) is fine.
          bad="$(printf '%s' "$RESULTS" | jq -r 'to_entries[] | select(.value.result=="failure" or .value.result=="cancelled") | .key')"
          if [ -n "$bad" ]; then echo "::error::gate job(s) did not pass: $bad"; exit 1; fi
          echo "all gate jobs passed or were skipped"
```

Branch protection requires a single check named `gate-ok`, regardless of how many packages or stacks the repo grows. Note the name differs from the single-stack scaffold's `gate / gate-ok`: that prefixed form is how GitHub names a job reached *through* a reusable workflow (caller job `gate` -> nested `gate-ok`), whereas here `gate-ok` is a top-level job in your own workflow, so its check is the bare `gate-ok`. Require that, not the per-package `backend / gate-ok` / `frontend / gate-ok` the facade calls emit. Because a path-filtered package is *skipped* (not failed), `gate-ok`'s `if: always()` keeps it from stalling the merge, and because the aggregator iterates over the `needs` context itself (rather than a hand-listed set), a package added to `needs` can never silently escape the gate. `foundry-init --mono` generates all of this; to change the package set later, delete the generated `gate.yml` + `bootstrap.yml` (the scaffold never clobbers) and re-run `--mono` with the full set of pairs.

## mise verb templates (`mise/`)

`ts` · `java` · `php` · `kotlin` · `dotnet` · `python` - each exposes the six verbs
(`fix`/`lint`/`typecheck`/`test`/`audit`/`gate`), gate sequential. `java` also pins
**PMD** (which can't be a `[tools]` entry - JVM launcher + jars, no OS-tagged asset)
via a `setup:pmd` task + `postinstall` hook + `_.path`, so it's provisioned by
`mise install` and on PATH, local and CI alike - no manual install. `ts`'s `typecheck`
fails when there is no `tsconfig.json` (a framework checker would otherwise pass having
checked only its own file types), and type-checks Deno code (e.g. Supabase Edge
Functions) with `deno check` over `FOUNDRY_DENO_PATHS`; Deno code found with that unset
fails the verb instead of going unchecked.

## Presets (`presets/`)

| Preset | Purpose |
|---|---|
| `habit-hooks/{ts,java,php,kotlin,dotnet,python}.toml` | Structural-smell config per stack; tests excluded; Java names its tuned ruleset via `-R`. The TS sensors shell out to `knip`, `ts-morph` and `jscpd`, so `foundry-init` adds those to the repo's `devDependencies` (caret-pinned, Renovate-bumped); seeding a baseline before they are installed captures a missing-tool error instead of real findings. |
| `habit-hooks/jscpd.json` | jscpd duplication-ignore list (the language-independent `generic` sensor reads it). Copied by `foundry-init` for the `ts` and `java` stacks. |
| `habit-hooks/java/guides/*.md` | Per-smell coaching (oversized-function, high-complexity, too-many-parameters, deep-nesting) - concrete "how to fix + don't game it" text that renders inline per finding, in-loop and CI. Drop into a repo's `.habit-hooks/java/guides/`. |
| `pmd/ruleset.xml` | Tuned Java ruleset (`ExcessiveParameterList` minimum 8). |
| `pmd/no-var.xml` | The no-`var` rule (diff-scoped in CI). |
| `typecheck/tsconfig.json` | Strict, check-only tsconfig for the `ts` stack, including src, scripts and tests; notes on extending a framework's strict preset and keeping Deno code out. Copied by `foundry-init`. |
| `gitleaks.toml` | Secret-scan allowlist starting point. |
| `renovate.json` | Dependency-update automation - the update path the pin-everything rule needs. |
| `code-standards.md` | Agent-facing clean-code standard (functions do one thing / SRP), tied to the deterministic smells. `@`-include into AGENTS.md/CLAUDE.md. |
| `collaboration.md` | Agent-facing working discipline - branch hygiene for parallel sessions (own branch off `origin/main`, one branch→one PR, rebase not merge). `@`-include into AGENTS.md/CLAUDE.md. |
| `agent-loop.md` | Agent-facing working *loop* - observe (run the oracle) → diagnose the real cause → act → verify/self-critique → repeat until green *and* honest; tiered in-loop/pre-push/CI; never game the metric. `@`-include into AGENTS.md/CLAUDE.md. |
| `ticket-schema.md` | The GitHub-Issue ticket the `feature` driver + `repo-align` claim - intent, acceptance-criteria checklist, scope, pointers; `agent:ready`/`working`/`blocked` label state machine. The checklist is what `verify` and spec-review walk. |
| `ISSUE_TEMPLATE/agent-feature.yml` | GitHub issue form enforcing the ticket schema (required fields, `agent:ready` label). Copy to a consumer's `.github/ISSUE_TEMPLATE/`. |

## Scripts (`scripts/`)

- `ruleset_guard.py` - per-entry, tightening-aware anti-gaming check.
- `npm-audit-ratchet.mjs` - ratcheted `npm audit` for the ts `audit` verb: fails on any critical not in `.audit-allowlist.json` and on stale entries, so accepted CVE debt can only shrink (npm audit has no native per-advisory ignore). Degrades to plain `npm audit --audit-level=critical` with no allowlist. Reads the report from stdin.
- `cut-release.sh` - cut a release in one deterministic command (version from the latest tag → CHANGELOG from conventional commits since it → tag + push → GitHub release → advance the `vN` alias; refuses a non-major bump on a breaking commit). Replaced release-please. Run locally on a clean `main`.
- `foundry-init.sh` - one-shot repo scaffold.
- `setup-labels.sh` - create the GitHub labels the workflows + ticket state machine need (agent:ready/working/blocked, align, ruleset-change, autofix). Idempotent; run by `foundry-init`.
- `foundry-pr-report` - one-shot, non-blocking PR check reporter: prints the bucket verdict for a PR's checks and, on failure, dumps the failing steps' logs via `gh run view --log-failed`; exits 0 (all passed/skipped), 1 (a check failed), or 2 (still pending). Trigger-agnostic by design, so a PR-authoring agent gets the actual failure text looped back without a blocking watch: call it once CI has finished, from whatever async trigger you wire up (a local post-push hook, a webhook-fired routine, or a background task that resumes the session). Needs `gh`. Copied by `foundry-init` into the consumer's `scripts/`.
- `jev/` - the **advisory** Jev layer: `client.mjs` (provider port lifted from jev-triage), `route.mjs` (pure routing/triage core), and `review.mjs` (runnable review pre-filter: `node scripts/jev/review.mjs [baseRef]` prints per-file `{review, lens, reason}` routing JSON). Near-free System-One decisions on the **proposer** side only: which diff hunks warrant deep review and on which lens. Opt-in via `JEV_API_KEY` (+ `JEV_PROVIDER`/`JEV_MODEL`/`TYPESAFE_AI_BASE_URL`); absent key ⇒ every caller fails open to current behavior (review all). **Never in the deterministic gate** - `boundary.test.mjs` reds the build if a gate workflow or mise verb references it; the `jev-scripts.yml` workflow runs the suite (`node --test scripts/jev/*.test.mjs`) on change. The non-secret knobs have a commented home in every mise template's `[env]` block (the "Jev (advisory layer)" group: `JEV_PROVIDER`, `JEV_MODEL`, `TYPESAFE_AI_BASE_URL`, `JEV_REVIEW_MIN_FILES`, and the downstream `JEV_TOOLCALL_TRIAGE` / `JEV_FEATURE_PRECHECK` hook toggles); the key itself stays in the shell, never in committed config.

## Agent half - `cmaintz-skills`

- **Skills:** `ship`, `review`, `repo-align`, `foundry-secret`, `feature` (backlog-driven
  driver: claim a ticket → isolated worktree → bounded gate-fix loop → behavioural
  verify → `ship`; `/feature <ref>` supervised or `/feature` puller, `/loop /feature`
  for semi-auto. See `designs/backlog-feature-driver.md`).
- **Hooks:** `habit-hooks-guard` (Stop, smells), `auto-format` (PostToolUse, per-edit
  prettier/eslint), `format-java-stop` (Stop, ratcheted Spotless),
  `typecheck-stop` (Stop, type errors), `guard-generated-files` (PreToolUse, blocks hand-editing snooze/suppressions), `pre-push` (git hook). All portable sh.

## Cross-cutting mechanisms

- **Deterministic oracle / probabilistic proposer** - the gate decides; the model proposes.
- **Ratcheting** - baselines that may only shrink (ESLint suppressions, snooze, coverage floors, Spotless/Semgrep/PMD diff-scoping).
- **`ruleset-guard`** - a source+ruleset PR that loosens the gate needs a `ruleset-change` label; merge-base-scoped so a stale base can't false-flag.
- **Placement triad** - in-loop (hooks) / pre-push (`/ship`, git pre-push) / CI, one rule set, no drift.
- **CI split + branch protection** - gate/quality/security/deploy/bootstrap; the gotchas and the path-filter+aggregate pattern live in [OVERVIEW.md](./OVERVIEW.md) §13.
