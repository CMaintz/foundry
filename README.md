# foundry

Reusable CI workflows, `mise` task templates and config presets behind a single six-verb interface, so the same rule set runs while an agent edits, before you push, and on the PR.

## What problem this solves

When an AI coding agent (or a person) changes code, the checks that decide "is this good enough?"
usually live in several places that disagree: the editor, a pre-push hook, and CI each run
different tools with different settings. The result is work that passes locally and fails on the
pull request, and agents that fix one complaint only to trigger another.

![One rule set, three placements: in-loop Claude Code hooks while the agent edits, /foundry:ship or the git pre-push hook before code leaves the machine, and gate.yml plus security.yml on the pull request. Pre-push and CI run mise run gate (lint, typecheck, test, audit); the exit code decides and baselines only shrink.](docs/readme-visual.png)

## The method

Foundry is a small set of beliefs about how to let agents write code you can trust, turned into tooling.

**Deterministic is the oracle; probabilistic only proposes.** Linters, types, tests and scanners decide pass/fail. A model produces a *patch*, which is accepted only if the deterministic gate then passes. A model's claim that it fixed something is not evidence - the exit code is. The advisory Jev layer obeys the same rule: the gate may run Jev's own unit tests, but never calls Jev for a verdict, and a boundary test enforces it.

**One rule set, three placements.** A CI pipeline and a set of agent habits usually get built as two separate things. They should be one rule set, placed in three spots:

| Placement | When | Feedback to | Cost |
|---|---|---|---|
| In-loop | while the agent edits | the agent, mid-task | free, already in session |
| Pre-push | before code leaves the machine | you | free |
| CI | on pull request | the permanent record | free tier |

Run different rules in each and you get "passes locally, fails in CI", plus a failure mode specific to agents: the agent fixes what the hook reported, CI complains about something else, the agent fixes that and regresses the first.

**Ratchet, don't gate.** Retrofitting linters onto a real codebase means everything is red on day one, and you abandon it in week two. Record the existing violations as an accepted baseline that may only ever shrink. ESLint 9.24+ (`--suppress-all` / `--prune-suppressions`) and habit-hooks (`habit-snooze`) both have this built in.

**Guard the guards.** An agent under pressure will find the cheapest way to green, and the cheapest fix for `high-complexity` is `// eslint-disable-next-line`. `ruleset-guard` fails a PR that loosens a baseline alongside source, adds an inline suppression or deletes a test, unless a human labels it (`ruleset-change` or `suppression`) and says why.

**The ticket is the real prompt.** An agent's output is capped by its input, so tickets have a schema: intent, a checklist of acceptance criteria, a Definition of Done, scope boundaries and pointers. Acceptance criteria are best written as executable Given-When-Then scenarios (acceptance-test-driven development): the contract the agent works to, with nothing left to guess. A ticket becomes `agent:ready` only once its owner has explicitly approved it.

**Green is not correct.** A passing gate says the code is clean, not that it does the job. The work is checked item by item against the ticket's acceptance criteria and Definition of Done, then reviewed by a fresh-context agent that sees only the diff and the ticket. Model reviewers advise; only deterministic checks block.

**Foundry eats its own cooking.** Foundry runs its own six verbs from a root `mise.toml`, so the same `feature` and `ship` loop works on Foundry tickets.

The full write-up, from beliefs to the agent loop, ticket schema, team rollout and evaluating the harness: [Agentic Engineering: Harnesses and Workflows for Teams](./docs/agentic-engineering/README.md). Design rationale: [DESIGN.md](./docs/DESIGN.md).

## How it fits with cmaintz-skills

**[cmaintz-skills](https://github.com/CMaintz/cmaintz-skills)** is the agent half, a Claude Code plugin. Its skills drive the loop around this gate (`spec` writes the ticket, `feature` loops on `mise run gate` until green, `ship` reviews and opens the PR) and its hooks are the in-loop placement. Its `codemap` skill gives `spec`, `feature` and `review` a cited, SHA-stamped map of the repo; a Foundry `codemap:check` task that flags dead citations is planned ([#111](https://github.com/CMaintz/foundry/issues/111)). Foundry decides *whether* a change is good enough; cmaintz-skills is how an agent gets it there. The seam between them is [CONTRACT.md](./CONTRACT.md), which is copied verbatim into both.

> **New here? Read [OVERVIEW.md](./docs/OVERVIEW.md)** - the full narrative tour of how the gates, habit sensors, skills, and the self-improving `learn` loop fit together.
>
> **[FEATURES.md](./docs/FEATURES.md)** is the canonical inventory of everything Foundry provides - and the backport checklist: anything non-language-specific built in a consumer repo comes back here.

## The verbs

```bash
mise run fix        # auto-fix what is mechanically fixable
mise run lint       # style + structural smells
mise run typecheck  # static types
mise run test       # tests + coverage floor
mise run audit      # vulnerabilities, secrets, SAST
mise run gate       # all of the above, in order. The oracle.
```

Callers invoke **verbs, never tools**. That's what lets one skill library serve a Kotlin repo and a React repo. Full rules in [CONTRACT.md](./CONTRACT.md).

Every verb in `gate` runs through `foundry-verb-wrap`, which logs its time and result for cmaintz-skills' `loop-report` without changing the outcome. Auxiliary tasks sit next to the verbs, off the contract:

- `smells` - the repo's pinned habit-hooks structural-smell check.
- `test:flaky` - tests with quarantined flakes reported but not gating (`foundry-flaky`, shrink-only `flaky-baseline.json`).
- `arch` (ts, python) - architecture fitness: no cross-layer imports, no cycles.

## Using it in a repo

Fastest path - the scaffold copies the templates + presets and generates the caller workflows, then prints the branch-protection checklist:

```bash
curl -fsSL https://raw.githubusercontent.com/CMaintz/foundry/main/scripts/foundry-init.sh -o foundry-init.sh
bash foundry-init.sh java                             # single stack: ts | java | php | kotlin | dotnet | python
bash foundry-init.sh --mono java:backend ts:frontend  # monorepo: one stack:dir pair per package (ts|java|php|dotnet)
```

Or wire it by hand - a `mise.toml` with the six verbs (see [templates/](./mise/)) plus a caller workflow that pins the **facades** and passes your stack:

```yaml
# .github/workflows/gate.yml
jobs:
  gate:
    uses: CMaintz/foundry/.github/workflows/gate.yml@v2
    with:
      stack: java              # ts | java | php | dotnet | python
      working_directory: "."   # monorepo? call this job once per package
```

### The public API - two facades

Pin **these**, whatever the stack. They dispatch internally to the per-stack workflows, so the files you pin never change when a stack is added or an internal is renamed. Require their `*-ok` aggregate checks in branch protection.

| Facade | What it runs | Key inputs |
|---|---|---|
| [`gate.yml`](./.github/workflows/gate.yml) | the language gate (six verbs, one-per-step with fix summaries) + structural smells; Java adds an opt-in `spotbugs` job | `stack` (ts/java/php/dotnet/python), `working_directory`, `spotbugs` |
| [`security.yml`](./.github/workflows/security.yml) | language-agnostic: secret scan + `ruleset-guard` + diff-aware SAST | `ruleset_paths`, `source_paths`, … |

Auxiliary reusables you call directly (not behind a facade):

| Workflow | What it runs |
|---|---|
| `web.yml` | max-file-length gate for HTML/CSS |
| `bootstrap.yml` | regenerates the habit-hooks snooze baseline on Linux and opens a PR |
| `ratchet-report.yml` | PR comment showing how the accepted-debt baselines moved |
| `autofix.yml` | add an `autofix` label to a PR → runs `mise run fix`, commits + pushes the result |
| `changes.yml` | monorepo path classifier - builds only the packages a PR touched (fail-safe: an unclassified path rebuilds everything) |

**Monorepo (many stacks in one repo):** call `gate.yml` once per package (each with its own `stack` + `working_directory`), wrap them in one `gate-ok`, and gate each on `changes.yml`. Branch protection requires a single check named `gate-ok` - a plain `gate-ok`, **not** the `gate / gate-ok` of the single-stack scaffold: that prefixed form only appears for a job reached through a reusable workflow, and here `gate-ok` is a top-level job in your own workflow. `foundry-init --mono java:backend ts:frontend` generates all of it. Full template: [FEATURES.md](./docs/FEATURES.md#monorepo-one-repo-many-stacks).

> Internals are `_`-prefixed (`_java.yml`, `_ts.yml`, `_php.yml`, `_dotnet.yml`, `_python.yml`, `_guards.yml`, `_semgrep.yml`) - the facades' implementation. Don't pin them directly; they can change between minor versions.

Split them across `gate.yml` / `quality.yml` / `security.yml` / `bootstrap.yml` (see [OVERVIEW.md](./docs/OVERVIEW.md) §13).

### Auto-merging the baseline prune PR

`bootstrap.yml` opens a PR whenever a prune shrinks the snooze baseline, and arms auto-merge on it. Opened with `GITHUB_TOKEN`, though, GitHub treats `github-actions[bot]` as a first-time contributor: the PR's checks wait for someone to click **Approve**, so nothing merges on its own. To skip that, give it a GitHub App of your own to open the PR as.

<details>
<summary>Setting up the GitHub App</summary>

1. Create the App at <https://github.com/settings/apps/new> (or your org's settings):
   - **Webhook:** untick **Active**.
   - **Repository permissions:** Contents *Read and write*, Pull requests *Read and write*. Leave the rest at *No access*.
   - **Where can this GitHub App be installed?** *Only on this account*. Every consumer makes their own; nobody else needs yours.
2. On the App's page, copy the **Client ID** and **Generate a private key** (a `.pem` downloads).
3. **Install App** → pick the repos that run `bootstrap.yml`.
4. Give each repo the ID and key:

   ```bash
   gh variable set BOOTSTRAP_APP_CLIENT_ID -R <owner>/<repo> --body "<client id>"
   gh secret set BOOTSTRAP_APP_PRIVATE_KEY -R <owner>/<repo> < path/to/key.pem
   ```

5. Pass them to the workflow:

   ```yaml
   jobs:
     bootstrap:
       uses: CMaintz/foundry/.github/workflows/bootstrap.yml@<sha> # vX.Y.Z
       permissions:
         contents: write
         pull-requests: write
       secrets:
         app_private_key: ${{ secrets.BOOTSTRAP_APP_PRIVATE_KEY }}
       with:
         habit_hooks_plugin: habit-hooks-typescript
         app_client_id: ${{ vars.BOOTSTRAP_APP_CLIENT_ID }}
   ```

</details>

Without the App it still works; the PR just says its checks need one approval. Repos also need **Allow auto-merge** on and required status checks on the base branch.

### Presets

Shared config and agent-facing docs the scaffold copies (or, for the docs, `@`-include straight into your `AGENTS.md` / `CLAUDE.md`):

| Preset | What |
|---|---|
| [`habit-hooks/<stack>.toml`](./presets/habit-hooks/) | structural-smell config per stack - tests excluded, the language-independent `generic` duplication check everywhere ([details](./presets/habit-hooks/README.md)) |
| [`habit-hooks/java/guides/`](./presets/habit-hooks/java/guides/) | per-smell coaching for the Java sensor - concrete "fix toward this", rendered inline in-loop *and* in CI |
| [`pmd/ruleset.xml`](./presets/lint/pmd/) · `pmd/no-var.xml` | tuned Java ruleset (`ExcessiveParameterList` ≥ 8) + the no-`var` rule |
| [`typecheck/tsconfig.json`](./presets/typecheck/tsconfig.json) | strict, check-only tsconfig for the `ts` stack, covering src, scripts and tests. The `ts` template's `typecheck` refuses to run without a tsconfig, and checks Deno code (Supabase Edge Functions) with `deno check` via `FOUNDRY_DENO_PATHS` |
| [`gitleaks.toml`](./presets/security/gitleaks.toml) · [`renovate.json`](./presets/renovate.json) | secret-scan allowlist starting point + the dependency-update path the "pin everything" rule needs |
| [`code-standards.md`](./presets/agent/code-standards.md) · [`collaboration.md`](./presets/agent/collaboration.md) · [`agent-loop.md`](./presets/agent/agent-loop.md) | agent-facing standing docs - clean code (functions do one thing / SRP), working discipline (branch hygiene + sub-agents), and the self-correcting loop (observe → fix the cause → verify → repeat until green *and* honest) |
| [`ticket-schema.md`](./presets/tickets/ticket-schema.md) · [`ISSUE_TEMPLATE/agent-feature.yml`](./presets/tickets/ISSUE_TEMPLATE/agent-feature.yml) | the GitHub-Issue ticket the `/foundry:feature` driver works - intent, an acceptance-criteria checklist, a Definition of Done, scope, pointers. Copy the template into a consumer's `.github/ISSUE_TEMPLATE/` |
| [`lint/ruff.toml`](./presets/lint/ruff.toml) · [`dotnet/Directory.Build.props`](./presets/dotnet/Directory.Build.props) | the python stack's default ruff hard gate, and the .NET build props the scaffold places |
| [`arch/`](./presets/arch/) | architecture-fitness rules per stack (dependency-cruiser, import-linter, ArchUnit) - [SETUP.md](./presets/arch/SETUP.md) |
| [`prompt-eval/`](./presets/prompt-eval/) | an offline regression harness for prompts and agent output, run under `test`; the fixture count may only grow |
| [`baselines/flaky-baseline.example.json`](./presets/baselines/flaky-baseline.example.json) | starting point for the `test:flaky` quarantine list |

### From ticket to PR - the `/foundry:feature` driver

Foundry answers *"when is a change done?"* - a green gate. The **`/foundry:feature`** driver is the thing in front of that - **ticket in, PR out** - the [`feature`](https://github.com/CMaintz/cmaintz-skills) skill in cmaintz-skills, specified in [designs/backlog-feature-driver.md](./docs/designs/backlog-feature-driver.md). Foundry ships the intake it consumes (the schema + issue template above). Tickets come from cmaintz-skills' `spec` skill or by hand. The driver:

1. **Claim** an `agent:ready` ticket - a GitHub Issue on the [`agent-feature`](./presets/tickets/ISSUE_TEMPLATE/agent-feature.yml) form ([schema](./presets/tickets/ticket-schema.md)) - flipping it to `agent:working` (atomic, WIP = 1) in its own worktree off `origin/main`, then reads the codemap slices the ticket touches when the repo has one.
2. **Loop to the gate** - implement → `mise run gate` → act on the failure + habit-hooks coaching → retry, *bounded* (≤ 5 cycles; bail early on no progress, posting the stuck state to the issue thread and flipping `agent:blocked`).
3. **Verify** the result against every acceptance criterion and Definition of Done item - green ≠ correct.
4. **Hand to `/foundry:ship`** - which re-gates, runs a fresh-context review against the linked issue, commits, and opens the PR. The driver never opens a PR itself, so there's one trusted path to `main`.

It re-implements none of the standards: the gate is the oracle, `ruleset-guard` + habit-hooks stop the loop gaming the metric, `/foundry:ship` is the handoff. Run it supervised - `/foundry:feature <ref>` - or as a backlog puller - `/loop <interval> /foundry:feature`.

### Versioning

Foundry follows semver on the reusable-workflow **interface** (workflow inputs and
the six-verb contract - not the internal steps):

- **patch** (`v1.0.1`) - a fix with no interface change.
- **minor** (`v1.1.0`) - a backward-compatible addition (a new workflow, a new
  optional input, a feedback improvement).
- **major** (`v2.0.0`) - a breaking change: an input renamed/removed, a verb's
  meaning changed, a workflow dropped. Only then must a consumer act.

Tag at **milestones** - a batch of merged PRs - not every commit; per-commit tags
are noise. Cut an immutable `vX.Y.Z` tag, then **move the `vX` alias** to it, so a
consumer pinning `@v1` rides non-breaking updates while `@v1.2.0` stays frozen.
Pin by SHA for maximum reproducibility (Renovate bumps it) or by `@v1` for
convenience. `CHANGELOG.md` records what each tag moved.

Cut a release with one command from a clean `main`:

```bash
bash scripts/cut-release.sh minor      # or major | patch | X.Y.Z  (--dry-run to preview)
```

It reads the current version from the latest tag (the only source of truth), builds
the `CHANGELOG` section from the conventional commits since that tag, tags + pushes,
creates the GitHub release, and advances the `vX` alias - deterministically, in one
auditable step. It **refuses** a non-major bump when it sees a breaking commit, so
semver can't silently slip. (This replaced release-please, whose separate manifest
state could desync from the tags.)

## Status

TypeScript and Java are the proven stacks (Java via the AutoApplicant pilot - Spring Boot + Angular + a browser extension). PHP, .NET and Python also have gate workflows behind the facade. Kotlin has a verb template and presets but no CI workflow yet. DESIGN.md §10 covers the rollout and §11 what's still open.

## Licence

MIT.
