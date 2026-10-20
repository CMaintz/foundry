# Foundry - how the whole thing works

A narrative tour of the system: the harness engineering, the gates, the habit
sensors, the skills, the loop that lets an agent get better at a codebase over
time, and the parts that are still rough. If you read one document, read this one.

For the rules themselves see [CONTRACT.md](../CONTRACT.md); for the canonical
feature inventory and the backport checklist see [FEATURES.md](./FEATURES.md).
[DESIGN.md](./DESIGN.md) is the original design brief (Sept 2026) and is now
partly historical - treat this file and FEATURES.md as the current state.

---

## 1. The one idea

A CI pipeline and a set of "AI coding standards" are usually built as two
separate things that slowly disagree with each other. Foundry's whole premise is
that they are **one rule set, run in three places**:

| Placement | When it runs | Who it talks to | What runs |
|---|---|---|---|
| **In-loop** | while the agent is editing | the agent, mid-task | a `habit-hooks` Stop hook |
| **Pre-push** | before code leaves your machine | you | `mise run gate` (via `/ship`) |
| **CI** | on every pull request | the permanent record | the same gate + guards |

Run *different* rules in each and you get "passes locally, fails in CI", plus a
failure mode unique to agents: the agent fixes what the hook flagged, CI
complains about something else, the agent fixes that and regresses the first
thing. One rule set, three placements, no drift.

## 2. The two repos and the one tool

Three moving parts, deliberately separated by who consumes them:

- **`foundry`** (this repo) - the CI half. Reusable GitHub Actions workflows,
  `mise` task templates, config presets, and the deterministic gate scripts.
  Consumed by *repositories*, by pinning two reusable workflows.
- **`cmaintz-skills`** - the agent half. Claude Code skills and hooks (`spec`,
  `feature`, `ship`, the habit-hooks Stop hook, the PR-create guard). Consumed by
  *Claude Code* as an installed plugin.
- **`habit-hooks`** - a third-party tool (Python, installed into a pinned venv),
  not written by us. It is the structural-smell sensor layer, and Foundry borrows
  its tool-independent smell vocabulary as a backbone.

The seam between `foundry` and `cmaintz-skills` is [CONTRACT.md](../CONTRACT.md),
copied verbatim into both. If those two copies ever need to differ, the split was
wrong. A change to the verb names or their meaning is the one thing that bumps the
major of *both* repos together; everything else (a stack, a preset, a skill) is
additive.

## 3. The verb interface - the thing that makes it polyglot

Every repo, whatever language, exposes the **same six verbs** through `mise`:

```
mise run fix        # auto-fix what is mechanically fixable (the only mutating verb)
mise run lint       # style + structural smells (non-mutating)
mise run typecheck  # static types
mise run test       # tests + coverage floor
mise run audit      # vulnerabilities, secrets, SAST
mise run gate       # lint -> typecheck -> test -> audit, in order. THE ORACLE.
```

Everything else in the system - CI, the git hooks, the skills - calls **verbs,
never tools**. A skill says `mise run lint`; it never says `eslint` or `phpstan`.
That indirection is the entire reason one skill library can serve a React repo and
a Kotlin repo: the smell vocabulary is language-independent, only the tool behind
each verb changes.

Two details that matter:

- **`gate` is a sequential `run` array, not mise `depends`.** `depends` runs
  prerequisites in parallel with no ordering guarantee, which scrambles the output
  and hides which check failed first. Every template says, in a comment, "do NOT
  add the verbs as `depends`." The one `depends` the gate carries is on
  `setup:foundry-scripts` (see Section 8), an idempotent safety net.
- **Verb tiers** ([docs/designs/verb-tiers.md](./designs/verb-tiers.md)): the six
  are tier-a (the contract). Tier-b is verb *composition* - `lint` folds in a
  `smells` task so the structural scan rides the same verb locally and in CI.
  Tier-c is auxiliary, opt-in, repo-local tasks that are explicitly *not* the
  contract: `arch` (architecture fitness), `spotbugs`, `novar`, `test:flaky`, the
  `setup:*` tasks. A seventh verb would have to be both universal and not fit any
  existing verb; none has qualified.

`mise` also pins the toolchain (`node = "22.14.0"`, the JDK, PHP, Python, etc.) in
the same file that defines the tasks, so "works on my machine" is closed by the
same mechanism that defines the verbs.

## 4. Deterministic vs probabilistic - who is allowed to decide

This is the load-bearing distinction in the whole design.

- **Deterministic layer = the oracle.** Formatters, linters, type checkers, tests
  + coverage, dependency/secret/SAST scanners. Pinned, reproducible,
  offline-capable. **These decide pass/fail. Nothing else does.**
- **Probabilistic layer = a proposer, never an authority.** An LLM's output is a
  *patch*. A patch is accepted only if the deterministic gate then passes from a
  clean tree. A model's *claim* that it fixed something is not evidence - the exit
  code is.

Concretely: an agent may run `mise run fix`, may act on habit-hooks' coaching, may
write code, but "done" is defined solely as a green `mise run gate`. The agent
proposes; the gate disposes.

Three probabilistic *roles* are kept deliberately separate (people mush them):

1. **Fixer** - given a failure + coaching, produce a patch. Bounded.
2. **Reviewer** - the things a linter genuinely cannot judge: naming, domain
   drift, "is this the right seam", spec compliance. **Advisory, never blocking.**
3. **Triager** - flaky vs real, dedupe, route to a ticket.

## 5. The gate, job by job

A consumer wires CI by pinning **two reusable facade workflows** and requiring
their aggregate checks. CI is **100% deterministic on purpose** - no model, no API
key, no secrets beyond the default token (see Section 11 for why).

- **`gate.yml` facade** - dispatches by `stack` (ts/java/php/dotnet/python) to the
  internal `_<stack>.yml`, runs `mise run gate` (the exact verb a developer runs
  locally), plus a `habits` structural-smell backstop job. Exposes a stable
  **`gate-ok`** aggregate check. An unknown stack fails loudly rather than passing
  silently.
- **`security.yml` facade** - secret scan (gitleaks over full history),
  `ruleset-guard`, and diff-aware SAST (semgrep `--baseline-commit`, default
  `p/ci`) in one call. Exposes **`security-ok`**.

The internal `_`-prefixed workflows are implementation and may change between
minor releases, so consumers pin the *facades*, never the internals. Branch
protection requires `gate-ok` and `security-ok` (never the heavy jobs directly;
see Section 17 for the required-check trap).

## 6. habit-hooks - coaching, not just failing

`habit-hooks` is the reflex layer. It wraps detectors (eslint, knip, ts-morph,
jscpd, PMD, phpmd, ruff, SonarAnalyzer) and maps their findings onto
**tool-independent smells**: `oversized-file`, `oversized-function`,
`too-many-parameters`, `high-complexity`, `deep-nesting`, duplication, dead code. A
smell means the same thing in Kotlin and PHP; only the detector differs. Test files
are excluded from smell scanning in every preset.

What makes it more than a linter: when it fails it emits **coaching** aimed at the
agent, and that coaching argues *against* mechanical compliance - "splitting a file
at line 200 into `foo-1.ts` and `foo-2.ts` satisfies the threshold while leaving
the real problem in place." That anti-gaming framing is why it is used to *teach*
an agent rather than only gate it. Java ships per-smell coaching guides under
`presets/habit-hooks/java/guides/`.

It runs in two placements:

- **In-loop:** a global **Stop hook** (`habit-hooks-guard.sh`, from cmaintz-skills)
  fires when the agent is about to finish, but only in repos that opted in by
  having a `.habit-hooks/` directory, so it is silent everywhere else and safe to
  install globally. It is a *Stop* hook, not *PostToolUse*, because habit-hooks
  costs ~25s cold (~6s warm), far too slow to fire after every edit, and it matches
  habit-hooks' own guidance: "run before considering work complete." In-loop scope
  is `--branch` (the changeset only), which also dodges the Windows ~8191-char
  command-line limit. The same hook opportunistically adds `.claude/worktrees/` to
  the repo's `.git/info/exclude`, because Claude Code's worktree isolation nests
  full repo copies under `.claude/worktrees/`, and an unignored copy would make
  `habit-hooks --branch` count every file in it as new, duplicated branch code.
- **CI:** the `habits` job inside the `gate.yml` facade.

The gate runs habit-hooks through the `smells` task folded into `lint`, calling the
pinned venv binary **by full path** (mise *appends* `_.path`, so an unpinned global
habit-hooks would otherwise shadow the pin). It degrades gracefully (skips) when a
repo has no `.habit-hooks/` config or no resolvable base ref, and fails hard *only*
when config and baseline exist but the binary is missing - a broken setup, which
should be loud rather than silently green.

Config lives in two places, and it matters which:

- **Global** (`~/.claude/settings.json`): the Stop-hook wiring only.
- **Per-repo** (`.habit-hooks/config.toml` + `.habit-hooks/snooze.json`): which
  plugins are on, and the accepted baseline of existing smells. Committed with the
  code. `config.toml` is shareable; `snooze.json` is not (it names real files and
  counts).

**The .NET sensor is ours.** `foundry-habit-hooks-dotnet` wraps a `dotnet build`
with SonarAnalyzer.CSharp active and maps its structural warnings (S104, S107,
S138, S1541, S3776) onto the same smell names, ratcheted via the snooze baseline.
The `.editorconfig` demotes those five rules to `suggestion` so the `-warnaserror`
typecheck verb does not hard-fail them; the sensor gates them instead.

## 7. Ratchets, not walls - and the guard that protects them

Retrofitting linters onto a real codebase makes *everything* red on day one, and
you abandon it in week two. So Foundry never gates on absolute cleanliness; it
**ratchets**:

- ESLint's native bulk suppression (`--suppress-all` / `--prune-suppressions`)
  records existing violations in `eslint-suppressions.json`.
- habit-hooks' snooze records existing smells in `snooze.json`.
- Coverage floors are set to *today's real number*, not an aspiration.

Each baseline is committed and may **only ever shrink**. Fix an `any`, and
`--prune-suppressions` removes it from the baseline permanently.

The obvious attack on any ratchet is to weaken the rule instead of fixing the code
- the cheapest fix for `high-complexity` is `// eslint-disable`. So
**`ruleset-guard`** (`scripts/ruleset_guard.py`, run as a CI job, not a Claude
hook) enforces mechanically. Its core property is that it is **per-entry, not
aggregate**: any single entry added or increased is a loosening, which defeats the
"offset attack" of fixing one violation while suppressing another to net zero on a
sum.

It is also **tightening-aware** - the risk is one-directional. *Loosening* needs a
human label (`ruleset-change`, or `suppression` for the inline/test cases);
*tightening*, or a change with no semantic effect (a pure CRLF/LF flip), passes
automatically. This is what lets `mise run fix` prune a baseline and ship that in
the same PR as the fix.

What it checks (all diffed from the **merge-base**, 3-dot, to avoid stale-base
phantom flags):

- **Baseline files** per-entry shrink-only: `eslint-suppressions.json`,
  `snooze.json`, ArchUnit freeze stores, coverage manifests.
- **Inline suppressions, tree-wide** (`inline`): every in-source suppression
  directive counted per `(file, directive)` at base vs head, because an inline
  `eslint-disable` / `@ts-ignore` / `# noqa` / `@SuppressWarnings` /
  `#pragma warning disable` stops the tool emitting, so the baseline never grows and
  the file-guard sees nothing. The regexes are assembled from fragments so the
  script never contains a directive literally (else it would flag its own source).
- **Config demotions** (carried inside the inline scan, because a config-only PR
  dodges the baseline-file guard): an editorconfig `severity = none`, a tsconfig
  `"strict": false`, a csproj `<NoWarn>`.
- **Deleted tests** (`tests`): test-definition count per file, inverse - a file
  with fewer test defs at head than base lost coverage. The coverage floor is the
  backstop for weaker-but-present tests.

### What counts as a gate-defining file - and who watches it

Governance is split across three enforcement points by *when* they run - a
client-side hook (cmaintz-skills), the CI guard (`_guards.yml`), and the
regenerator (`bootstrap.yml`):

| File | Controls | Protected by |
|---|---|---|
| `snooze.json` | structural-smell baseline | **hook** blocks hand-edits (incl. Bash writes) - **ruleset-guard** blocks growth without the label - **bootstrap** regenerates (prune only shrinks) |
| `eslint-suppressions.json` | lint baseline | same three |
| `.jscpd.json` | which paths the duplication sensor scans | **ruleset-guard** - widening the ignore list alongside source needs the label |
| `pmd/ruleset.xml`, thresholds, `mise.toml`, workflows | rule definitions / gate wiring | **ruleset-guard** - direction cannot be proven, so any change alongside source needs the label |
| `ruleset_paths` regex | *which* files ruleset-guard treats as gate-defining (this table's first column) | the `guards` input default, or a consumer override - **keep it in sync when you add a guarded file** |

The recurring failure mode: a *new* gate-defining file (like `.jscpd.json`) is not
added to `ruleset_paths`, so widening it slips past the guard. When you introduce
one, add it to the regex in the same change. The default regex is duplicated in
`security.yml` and `_guards.yml`, so both copies move together.

## 8. Provisioning - what is cached, not vendored

The north star is that a consumer vendors as little as possible, so upstream fixes
flow without a re-sync. Two things are fetched at a pinned ref rather than copied
into each repo:

- **The gate scripts** (`foundry-verb-wrap`, `foundry-flaky`,
  `npm-audit-ratchet.mjs`). Each template has a `setup:foundry-scripts` task that
  fetches them into `$HOME/.local/opt/foundry-scripts-<FOUNDRY_SCRIPTS_REF>` and
  puts that directory on `_.path` **cache-first**. It is offline-safe: zero network
  calls when every script is already present at the ref; a ref bump needs the
  network once. `FOUNDRY_SCRIPTS_REF` is a Renovate-tracked pin
  (`# renovate: datasource=github-tags depName=CMaintz/foundry`). Which scripts a
  stack fetches differs: ts fetches all three, java fetches verb-wrap + flaky, and
  python/dotnet/php/kotlin fetch only verb-wrap.
- **`ruleset_guard.py`**. The security and ratchet workflows sparse-checkout it from
  `job.workflow_repository @ job.workflow_sha` into `.foundry/`, so the guard logic
  and the workflow that runs it always move together at the exact pinned ref.

Still vendored in a consumer (copied by `foundry-init.sh`, which never clobbers on
re-run): `mise.toml`, `.habit-hooks/config.toml`, `.gitleaks.toml`, `renovate.json`
(a two-line file that extends Foundry's shared preset), the language presets
(tsconfig / ruff.toml / PMD rulesets / Directory.Build.props / .editorconfig), the
caller workflows, and the coaching guides. The agent-only PR and loop scripts live
in the plugin, not here, and are deliberately *not* vendored.

## 9. Telemetry - making the loop legible

Every verb in every one of the six templates is wrapped by `foundry-verb-wrap`,
which times the command, captures its exit code, and appends one JSONL line
(`ts, verb, scope, placement, exit, duration_ms`) to a gitignored
`.foundry/telemetry.jsonl`. It **always propagates the verb's real exit code** -
telemetry failure can never change the outcome. `placement` is inferred from the
environment (`ci` when `$CI`, else `manual`, or a hook-set value); `scope` is
`changed` when `FOUNDRY_SINCE` is set, else `whole`.

The `/loop-report` skill (cmaintz-skills) reads that file offline and answers: is
the loop converging or **thrashing** (a verb that passed and then failed again),
which verb is the time sink, and how many `gate` rounds a change took. It can fold
in CI outcomes via `gh run list`. It never decides pass/fail. Its smell-trend
signal is a planned follow-on; today the thrash signal is derived from verb
pass/fail regressions only. Design:
[docs/designs/loop-telemetry.md](./designs/loop-telemetry.md).

## 10. The skills - and the spec -> feature -> ship loop

The practice layer is thin on purpose, because most of it is written well by
others and installed as sibling plugins (mattpocock's skills, Ivett's skills,
habit-hooks). Foundry's own plugin (`cmaintz-skills`) adds the pieces that touch
the gate directly. The three layers stay cleanly divided:

- **Reflex** -> hooks (habit-hooks, auto-format, the PR guard). Involuntary.
- **Practice** -> skills (`spec`, `feature`, `ship`, `review`). Invoked, procedural.
- **Standing context** -> `AGENTS.md` + `CONTEXT.md`. Ambient shared vocabulary.
  (`CLAUDE.md` is a one-line include of `AGENTS.md`, so Codex/Gemini/Cursor read the
  same source.)

### The loop

Our own skills implement a ticket-in, PR-out loop, and the acceptance-criteria
`- [ ]` checklist is the artifact threaded through all three stages:

1. **`spec`** - a short Socratic back-and-forth turns a rough idea into a
   schema-complete, testable GitHub Issue labelled `agent:ready`. Never writes code.
2. **`feature`** - claims a ticket (atomic label flip + assign, WIP of 1), works it
   in an isolated `git worktree`, runs the bounded inner loop `fix -> habit-hooks ->
   gate` (max ~5 cycles, bails after 2 no-progress rounds), then verifies each
   acceptance criterion behaviourally. Hands off to `ship`; never opens a PR itself.
   Run `/feature <ref>` supervised, or bare `/feature` as a puller for the next
   ready ticket (wrap in `/loop` for semi-auto).
3. **`ship`** - the sole sanctioned path from working tree to PR:
   `mise run fix` -> habit-hooks coaching -> **`mise run gate` must be green** ->
   a fresh-context `review` -> a conventional commit -> open the PR and watch CI in
   one non-blocking step via `foundry-ship-pr`.

Supporting skills: **`review`** (one reviewer, three fresh-context lenses -
correctness, standards, spec - scaled by diff size and an effort dial; advisory
only), **`repo-align`** (an incremental campaign to grind a repo up to standard one
small PR at a time, targets picked by `hotspot-rec`), **`pr-ci-watch`** (the
non-blocking CI watch), **`foundry-secret`** (triage a gitleaks finding; secrets are
never ratcheted - allowlist a false positive, or rotate-then-purge a real one), and
**`loop-report`** (Section 9).

### Review runs in a fresh context

Step 4 of `ship` dispatches to a sub-agent that sees only the diff and the spec,
never the conversation that wrote the code. An agent reviewing its own work reviews
its *intent*, not its *diff*. Installing everything leaves three things called "code
review"; they layer most-specific first (a repo-local `build-project-review` skill
-> mattpocock's `code-review` -> the built-in `/code-review`) and namespace as
`plugin:skill`, so nothing collides.

### The PR-create guard - how the sanctioned path is enforced

A `PreToolUse` hook (`guard-pr-create.sh`) watches the Bash tool and blocks a bare
`gh pr create` (matched as three consecutive whole words, so `gh pr checks/view/
edit` and `git push` pass untouched), pointing the agent at `foundry-ship-pr`
instead. The enforcement is **subprocess isolation, not a token**: a `PreToolUse`
hook only ever sees the agent's own tool call, never a child process, so the only
legitimate way to open a PR is to invoke the script - which first runs the whole
ship sequence (gate + review + CI watch). `foundry-ship-pr` takes the PR body and
title from *files*, never the command line, so prose that mentions `gh pr create`
cannot trip the guard. `foundry-pr-report` is the reusable, non-blocking verdict
core (prints a check table, dumps failing logs, exits 0 pass / 1 fail / 2 pending).

Known gap, by design-limit rather than oversight: the hook watches one tool's
command text, so a different tool, a `gh api` call, or the script invoked directly
all sidestep it. It is a guardrail against drift, not a security boundary; the hard
boundary is branch protection requiring the CI gate (see Section 17).

## 11. Cost and the trust boundary

Running a model on every push is slow and metered, and a CI-side agent needs an API
key *and* write access on branches an agent authored - the worst corner of the
`pull_request_target` footgun family. Foundry's resolution is to **pull the work to
the local session instead of pushing the model into CI**: review happens at `/ship`
time locally (where the session is already paid for under a flat subscription), and
anything external is imported with `gh pr checkout` / `gh issue view`. The result:
no API key ever enters CI, so CI stays 100% deterministic, fast, and actually
trusted.

## 12. The self-improving loop - `learn`

This is what makes the system get *better* rather than only stay clean. Ivett's
`learn` skill reflects on a session and routes each lesson to the store that will
actually **enforce** it, in priority order:

1. **a deterministic hook / check** - enforcement, so the mistake becomes impossible
2. **`AGENTS.md` / `CLAUDE.md`** - standing context
3. **a new skill** - a reusable procedure
4. **auto-memory** - last resort

That ordering *is* the project's thesis expressed as a skill: prefer the placement
that makes a mistake impossible over the one that merely reminds you not to make it.
A one-off fix this session becomes a rule the next session cannot skip. `learn` is
model-invoked (not a hook), so the practice is to run `/learn` at session
boundaries, before anything gets written to memory.

```
work -> habit-hooks flags a smell -> agent fixes it -> /learn decides:
  "this class of mistake should be impossible" -> new deterministic check
  -> next time, the gate catches it before a human ever sees it
```

## 13. Flaky-test triage

`foundry-flaky` (a Python 3 script, despite the extensionless name) keeps a flaky
test from either blocking the gate or being silently ignored. It parses JUnit XML
(Gradle / JUnit / PHPUnit / pytest), vitest JSON, and **TRX** (dotnet
`--logger trx`), so four of the stacks are pure wiring and only dotnet needed a new
parser. Three subcommands: `gate` (fails only when a *non-quarantined* test failed;
a quarantined failure is logged but does not gate), `classify` (reruns failures to
split flake from real), and `prune` (re-arms a quarantined test once it has been
green for N consecutive runs). The quarantine list `flaky-baseline.json` is
committed and shrink-only, like every other baseline. It is exposed as the opt-in
tier-c `test:flaky` task, not on the gate. Design:
[docs/designs/flake-triager.md](./designs/flake-triager.md).

## 14. Setup - onboarding a repo

1. **Scaffold the gate.** `bash foundry-init.sh <stack> [workdir]` (or
   `--mono <stack:dir> ...` for a monorepo) fetches the `mise` template, the
   habit-hooks config and presets, the caller workflows (pinned to `FOUNDRY_REF`),
   and the repo-level files: `.gitleaks.toml`, a renovate config that extends the
   shared preset, a PR template, labels, and `.gitignore` entries for `.foundry/`
   and `.claude/worktrees/`. It never clobbers, so re-running it is safe.
2. **Install the toolchain.** The first `mise install` runs the `postinstall` hook,
   which runs the setup tasks in order (`setup:habit-hooks` builds the pinned venv,
   `setup:foundry-scripts` populates the script cache, plus `setup:pmd` or
   `setup:pytools` where relevant). CI does the same through `jdx/mise-action`.
3. **Install the plugin** for the agent half:
   `/plugin marketplace add CMaintz/cmaintz-skills` then
   `/plugin install foundry@cmaintz`. Skills land namespaced (`/foundry:ship`,
   `/foundry:feature`, ...).
4. **Register the hooks by hand.** The plugin has no `hooks.json`, so `/plugin
   install` gives you the skills but *not* the hooks. Copy `hooks/` into
   `~/.claude/hooks/` and add the registration JSON from the plugin README to
   `~/.claude/settings.json` (on Windows, use the full `bash.exe` path). This is the
   single biggest piece of onboarding friction.
5. **Wire branch protection.** Require the `gate-ok` and `security-ok` aggregate
   checks, turn on "require branches to be up to date" (strict mode), and do *not*
   require `bootstrap` (it is `workflow_dispatch` only). See Section 17 for the
   gotchas.

The gate works without the plugin; the plugin needs a Foundry-onboarded repo (every
skill stops early if `mise run gate` is not defined).

## 15. Where everything lives (quick map)

```
~/.claude/settings.json          # global: the habit-hooks Stop hook + PR-guard wiring
~/.claude/hooks/                 # the hook scripts (copied from the plugin by hand)
$HOME/.local/opt/
  foundry-scripts-<ref>/         # cached gate scripts (verb-wrap, flaky, npm-audit)
  <plugin>-<ver>/                # the pinned habit-hooks venv

<repo>/mise.toml                 # the six verbs + the pins + setup tasks for this repo
<repo>/.habit-hooks/             # config.toml + snooze.json (the smell baseline)
<repo>/eslint-suppressions.json  # the lint baseline (ratchet)
<repo>/.foundry/                 # gitignored: telemetry.jsonl, pr-url, flaky streaks
<repo>/.github/workflows/        # callers pinning foundry's gate.yml + security.yml facades
<repo>/AGENTS.md                 # standing context (CLAUDE.md @-includes it)

foundry/                         # reusable workflows, mise templates, presets, gate scripts
cmaintz-skills/                  # skills + hooks + agent-only PR/loop scripts, as a plugin
```

## 16. Monorepos - lessons from a Java/Spring + Angular pilot

Applying Foundry to a real polyglot monorepo (a Spring Boot backend + Angular
frontend + a browser extension) surfaced patterns worth codifying:

- **Verbs are namespaced per package.** One root `mise.toml` exposes
  `backend:gate`, `frontend:gate`, etc., plus an aggregate `gate`. CI runs each
  package's gate as its own job.
- **habit-hooks is per package, not per repo.** Its TypeScript detectors
  (eslint/knip/ts-morph/jscpd) resolve from the package's own `node_modules`, so the
  config and snooze baseline live in `frontend/.habit-hooks/`, and the sensor runs
  *from* `frontend/`. Backend Java/PMD lives in `backend/.habit-hooks/`.
- **Generate the smell baseline in CI, not locally.** On Windows the full-repo file
  list blows the ~8191-char command-line limit, so a manual `workflow_dispatch` job
  generates each `snooze.json` on Linux and commits it. The per-package smell jobs
  soft-pass until their baseline exists.
- **In-loop scope is `--branch`, not `--all`.** The Stop hook checks only the
  changeset - correct for "flag what you touched", and it dodges the Windows limit.
- **Dependency audit needs a lockfile, generated on demand.** osv-scanner reads a
  `gradle.lockfile`; enable Gradle dependency locking but keep the lockfile
  gitignored and regenerate it in the audit job, so lock drift never breaks the gate.
- **Ratchet by diff where a baseline file is overkill.** Spotless
  (`ratchetFrom origin/main`), Semgrep (`--baseline-commit`) and the no-`var` PMD
  rule (CI checks only changed files) all enforce on new code while leaving legacy
  untouched - the ratchet, without a committed baseline.
- **Integrate, don't replace, existing CI.** The pilot kept its Docker image-publish
  job verbatim and only added Foundry's gate + guard jobs alongside.

## 17. The split, and wiring branch protection

A consumer does not put everything in one `ci.yml`. Split by *cadence and blast
radius* into separate workflow files, each composing foundry's reusable pieces:

| File | Calls (facade) | Trigger |
|---|---|---|
| `gate.yml` | `gate.yml` facade - `with: { stack, working_directory }`, once per package; includes structural smells | PR + push |
| `security.yml` | `security.yml` facade - secrets + ruleset-guard + SAST in one call | PR + push |
| `bootstrap.yml` | `bootstrap.yml` - baseline refresh | `workflow_dispatch` |
| `deploy.yml` | image publish / release - **push-to-main only** | push |

Why split, not one file: `needs:` cannot cross workflow files, so unrelated jobs do
not serialise; a slow quality run does not gate a fast security result; and each
file has one obvious trigger. **Keep `deploy` push-only** - a deploy job under
`pull_request` shows up as a permanently *skipped* check, which is noise and can
wedge branch protection.

### Speed: cancel superseded runs, and skip work that cannot be affected

- **`concurrency` lives in the caller, not the reusable** (a reusable workflow
  cannot set it for you). Give each caller `concurrency: { group:
  <name>-${{ github.ref }}, cancel-in-progress: true }` so a new push cancels the
  in-flight run instead of paying for both.
- **Path-filter what genuinely cannot be affected - but mind the required-check
  trap.** A *required* check that is path-filtered out is reported as `Expected` and
  never arrives, so the PR cannot merge. The working pattern is a single
  always-running **aggregate** job that branch protection requires, which `needs:`
  the real jobs and passes when they either succeed or are legitimately skipped:

  ```yaml
  jobs:
    gate:   { if: ..., uses: ... }        # heavy, may be skipped by an inner filter
    gate-ok:                               # THIS is the required check
      needs: [gate]
      if: always()
      runs-on: ubuntu-latest
      steps:
        - run: '[ "${{ needs.gate.result }}" != "failure" ] || exit 1'
  ```

  Require `gate-ok`, never the heavy job directly. Skipped is not failed, so a docs
  PR goes green without running the gate, and a real failure still blocks.
- **Consider dropping the `push:main` run entirely - it is usually redundant.** The
  next PR's gate runs `mise run gate` against current main anyway, so a real break
  surfaces one PR later; with rebase-merge the merged commit is also the code the PR
  gated. Measure before assuming value: `gh run list --branch main --event push`.

### Branch protection - the gotchas that cost a pilot a day

- **Required check names must match the job's `name:` string *exactly*.** Protection
  matches on the rendered check name, not the job id. Rename a job and the old
  required check never reports - PRs hang "Expected" forever. Update protection and
  the job name in the same change.
- **A `workflow_dispatch`-only job never appears as a PR check** - so do not add
  `bootstrap` to required checks; it would block every PR waiting on a run that is
  not coming.
- **A PR opened with `GITHUB_TOKEN` waits for approval.** GitHub treats
  `github-actions[bot]` as a first-time contributor, so a bot-opened prune PR sits at
  "awaiting approval" and auto-merge never fires. Give `bootstrap.yml` a GitHub App
  (`app_client_id` + `app_private_key`) and the PR is opened as the App instead.
- **Enable "require branches to be up to date" (strict mode)** so a PR is re-tested
  against the latest main before merge - this, plus the guard diffing from the
  merge-base, is what stops a stale base from sneaking a regression in or
  false-flagging an untouched file.

## 18. Releases

Foundry is semver-tagged, with a floating `vN` alias that consumers can pin to.
`bash scripts/cut-release.sh <major|minor|patch|X.Y.Z> [--dry-run]` reads the
current version from the latest git tag (the only source of truth - there is no
manifest to desync), builds the CHANGELOG section from conventional commits since
that tag, commits, tags, pushes, creates the GitHub release, and advances the `vN`
alias. It refuses a non-major bump when a breaking commit is present, and it must be
run on a clean `main` in sync with origin. It replaced release-please, which had
desynced its manifest into phantom major bumps; do not re-add it.

## 19. Language coverage and current limitations

**Coverage.** All six `mise` templates exist (ts, java, python, dotnet, php,
kotlin). TypeScript and Java are the proven, built-out stacks; PHP, .NET, and Python
have gate workflows behind the facade. **Kotlin is the outlier**: it has a verb
template and presets but *no* reusable CI workflow (it emits an inline
`mise run gate` job), no habit-hooks sensor (its smells ride inside `lint` via
detekt), and `foundry-init --mono` rejects it. Adding a language stays additive: a
new `mise` template plus a reusable workflow mapping that language's tools onto the
same six verbs and smell names, with nothing already built changing.

**Known rough edges** (worth knowing before you lean on them):

- **Kotlin is second-class** (above) and **`--mono` also rejects Python**, so a
  Python monorepo cannot be scaffolded by `foundry-init` today.
- **The two repos are version-skewed.** The plugin is tagged only `v1` while foundry
  is at `v2.x`, and the plugin has no CHANGELOG, despite the CONTRACT's "bump the
  major of both together" rule. Cosmetic today, but it undercuts the coupling story.
- **`ruleset_paths` is a manual, duplicated invariant.** A new gate-defining file
  must be hand-added to the regex, which lives in two workflow files. Forget it and
  widening that file slips the guard.
- **Pins are hand-maintained across many files.** `HABIT_HOOKS_VERSION`,
  `FOUNDRY_SCRIPTS_REF`, and the PMD version live in templates, facade input
  defaults, and Renovate comments that must agree. A current example of the drift
  risk: the `gate.yml` facade default PMD version and the `mise/java.toml` pin do not
  match.
- **The PR-create guard is a guardrail, not a boundary** (Section 10): a different
  tool or a direct script call sidesteps it. The real stop is required CI checks.
- **The Jev layer looks core but is not.** `scripts/jev/` (and the plugin's Jev
  hooks) are an advisory, opt-in layer fenced out of the gate by a boundary test;
  everything fails open without `JEV_API_KEY`.
- **DESIGN.md is historical in places** - old repo paths, workflow names that no
  longer match, and roadmap tooling (trivy, SBOM/provenance, Ruby/Swift/Rust/Go)
  that is not implemented. This file and FEATURES.md are the current state.
