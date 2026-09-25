# Foundry — Design Document

**Status:** Draft v0.1 · **Owner:** CMaintz · **Date:** 2026-09-07

A unified engineering gate and agent-habit system for personal software projects.

---

## 1. Purpose

Two goals that are usually treated as separate problems, and shouldn't be:

1. A CI/CD pipeline for hobby projects — linting, code sniffers, types, tests, security — that is **worth trusting** and **cheap to run**.
2. A set of deliberate habits for developing with AI agents, so that quality is a **reflex** rather than something remembered.

The thesis of this document: these are **one system in three placements**, not two systems.

### Non-goals

- Enterprise-grade release engineering. This is for hobby projects with one maintainer.
- Paying per-token for routine CI. Cost discipline is a first-class constraint (§8).
- Supporting every language at once. Coverage grows by adding sensor plugins (§7.3).

---

## 2. Core principle — one rule set, three placements

A single definition of "what good looks like in my code" must run in three places:

| Placement | Fires | Feedback to | Marginal cost | Latency budget |
|---|---|---|---|---|
| **In-loop** (agent hooks) | while the agent edits | the agent, mid-task | free — already in session | < 5s |
| **Pre-push** (`/ship`) | before code leaves the machine | the human | free | < 60s |
| **CI** (GitHub Actions) | on pull request | the permanent record | free tier | < 5 min |

**Why this matters.** If the three placements enforce different rules you get the classic
"passes locally, fails in CI" *plus* a worse failure specific to agents: the agent fixes what the
in-loop hook reported, CI then complains about something else, the agent fixes that and regresses
the first — thrash that burns tokens and produces churn commits.

**Consequence:** do not write a CI pipeline and separately write a hooks setup. Write **one gate**
behind a narrow interface, and call it from all three placements.

---

## 3. The verb interface (the contract)

Every repo, regardless of stack, exposes the same verbs. Everything else — CI, hooks, skills —
calls only these. This is the single most important design decision in the document, because it is
what makes the system polyglot without becoming a monolith.

```
mise run fix        # auto-fix what is mechanically fixable; never opinionated
mise run lint       # style + smells; non-mutating
mise run typecheck  # static types
mise run test       # tests, with coverage threshold
mise run audit      # secrets, SCA, SAST
mise run gate       # all of the above, the authoritative composite
```

**Tool choice: `mise`, not Make.** Two reasons.

1. Make is painful on native Windows; `mise` is not.
2. `mise` also **pins the toolchain** (node, jdk, php, python versions) in the same file that
   defines the tasks — so "works on my machine but not in CI" is closed by the same mechanism that
   defines the verbs, rather than by a second one.

`just` is an acceptable substitute if toolchain pinning is handled elsewhere, but `mise` doing both
is the reason to prefer it.

### Rule

> Skills and workflows invoke **verbs**, never tools. A skill says `mise run lint`. It never says
> `eslint`. This is what allows a Kotlin repo and a React repo to share one skill library.

---

## 4. Deterministic and probabilistic layers

The split is not "some checks are fuzzy." The split is **who is the oracle**.

### 4.1 Deterministic — the oracle

Reproducible, pinned, offline-capable, no model in the loop. This layer decides pass/fail.

| Category | Tooling |
|---|---|
| Format | prettier / ruff format / php-cs-fixer / ktlint |
| Lint and smells | eslint, phpcs + phpmd, ruff, PMD, detekt |
| Types | tsc, mypy, PHPStan/Psalm |
| Tests | vitest / pytest / PHPUnit / JUnit + coverage floor |
| Secrets | gitleaks |
| Dependencies | osv-scanner |
| SAST | semgrep |
| Containers | trivy |
| Commits | commitlint (conventional commits) |
| Supply chain | SBOM, SHA-pinned actions, provenance attestation |

### 4.2 Probabilistic — a proposer, never an authority

Model output is a **patch or an opinion**. It is accepted only if the deterministic gate then passes.
Three roles, kept deliberately separate because they are usually conflated:

| Role | Input | Output | Blocking? |
|---|---|---|---|
| **Fixer** | a gate failure + its coaching text | a patch | no — the *re-run gate* blocks |
| **Reviewer** | the diff + the linked issue/spec | comments | **never** |
| **Triager** | a failure | flaky / real / duplicate + a ticket | no |

The Reviewer covers exactly what a linter cannot: naming, domain-model drift, "is this the right
seam", spec compliance. Advisory by construction — the moment a model can block a merge, you start
arguing with it instead of shipping.

### 4.3 Two hard rules

**Rule 1 — the Fixer may not edit the ruleset.**
The cheapest fix for `high-complexity` is `// eslint-disable-next-line`. This is not a discipline
problem to be solved by asking nicely in a prompt; it is enforced **deterministically**: CI fails if
a change touches lint configs, `.habit-hooks/`, thresholds, or snooze files *and* touches source, in
the absence of an explicit human label. Ruleset changes are their own PR.

**Rule 2 — the gate re-runs after every model patch, from a clean state.**
The model's claim that it fixed something is not evidence. The gate's exit code is.

---

## 5. Habits: reflex, practice, and standing context

Kent Beck's framing — a good developer with great habits — cuts a specific way here. *A habit you
have to remember is not a habit.* Prose in `CLAUDE.md` is advisory and decays as context fills; a
hook is enforcement. Three distinct mechanisms, and picking the wrong one is why most "AI coding
standards" documents end up ignored:

| Layer | Mechanism | Character | Example |
|---|---|---|---|
| **Reflex** | hooks (habit-hooks, pre-commit) | involuntary, fires unbidden | "this function takes 7 parameters" |
| **Practice** | skills | invoked, procedural, has judgement | `tdd`, `diagnosing-bugs` |
| **Standing context** | `AGENTS.md`, `CONTEXT.md` | ambient, shared vocabulary | the domain model |

`career-ops` and `MDB` already use the `CLAUDE.md → @AGENTS.md` include pattern. That generalises:
**`AGENTS.md` is canonical, `CLAUDE.md` is a one-line include.** Keeps other agents (Codex, Gemini,
Cursor) working off the same source.

### 5.1 habit-hooks

The bridge between the two layers: deterministic detection whose *output is coaching text aimed at a
model* rather than a bare rule ID. Architecture is a Unix pipeline — `habit-sensors` runs detectors
and emits JSON findings; `habit-mapper` groups them by **smell** (a tool-independent category such as
`too-many-parameters`) and sets the exit code.

Facts confirmed from upstream, which shape the plan:

- **Native Windows support** — explicitly "no WSL, no Git Bash, no shell of any kind."
- **The ratchet already exists.** `habit-snooze --snooze` records today's findings as accepted so only
  *new* smells surface. The `snooze-until-changed` transformer exempts a violation only while its file
  is unchanged since the branch base — touch the file and its issues return. **Do not build this.**
- Requires Python 3.11+ / `uv` regardless of the project's own language.

The ratchet is the difference between this surviving contact with existing repos and being abandoned
in week two. Retrofitting a linter onto a real codebase without one means everything is red on day one.

### 5.2 Skill sources

Forking all three sets wholesale, per decision. The risk of adopting someone else's habits wholesale
is that the unused 80% becomes noise — but Ivett's two meta-skills specifically address that, which
is why the combination works where either alone would not.

| Source | Contributes |
|---|---|
| **mattpocock/skills** | breadth of practice: `tdd`, `diagnosing-bugs`, `research`, `code-review`, `codebase-design`, `domain-modeling`, `to-spec`, `to-tickets`, `triage`, `prototype`, `wizard`, `handoff` |
| **habit-hooks** | the reflex layer + the smell vocabulary |
| **devill/ivetts-skills** | the *flywheel*: `learn`, `build-project-review`, `hotspot-rec` |

Why Ivett's set is load-bearing rather than a nice-to-have:

- **`learn`** routes a session learning to *a deterministic hook first*, `CLAUDE.md` second, a new
  skill third, discard fourth. That ordering is the whole thesis of this document expressed as a
  skill, and it is how borrowed habits gradually become yours.
- **`build-project-review`** generates a *repo-local* review skill distilled from your own review
  history and enforced configs — with a good verification rule: a generated rule that loses its
  supporting quote is discarded as invented rather than distilled.
- **`hotspot-rec`** nominates design work from git history (churn × size × temporal coupling) under
  the principle *"the metrics nominate, they never decide"* — the same deterministic-proposes /
  human-disposes split as §4.

**Known collision:** three things named some variant of `code-review` (Claude Code built-in,
Pocock's, Ivett's `build-project-review`). Plugin skills namespace as `plugin:skill`, so this is
survivable; budget one session to disambiguate and decide which is bound to `/ship`.

---

## 6. The `/ship` flow

Pre-PR review, run locally. This is the highest-leverage placement in the system: it moves review
left of the PR entirely, and in doing so makes a CI-side agent nearly redundant.

```
/ship
 │
 ├─ 1. mise run fix              deterministic auto-fixes land silently
 ├─ 2. habit-sensors | habit-mapper
 │        └─ coaching output → agent fixes the smells
 ├─ 3. mise run gate             ◀── MUST BE GREEN. the oracle, not the agent's opinion
 ├─ 4. agent review of the diff against the linked issue
 │        └─ fresh-context subagent (see below)
 ├─ 5. commitlint-conformant commit
 └─ 6. gh pr create
```

**Step 4 must run in a fresh context.** An agent reviewing work it just wrote has a genuine and
well-known blind spot: it reviews its *intent* rather than its *diff*. Mitigation — dispatch the
review to a subagent that sees only the diff and the spec, never the conversation that produced the
code. Pocock's `code-review` already fans out to parallel sub-agents, so this is mostly free.

---

## 7. Polyglot strategy

### 7.1 Why not one big pipeline

Modularity here is not an aesthetic preference — it falls out of an observation: **the smell
vocabulary is language-independent while the detectors are not.** `too-many-parameters` means the
same thing in Kotlin and PHP; only the tool that spots it differs. So the shared spine is the
*vocabulary*, and detectors plug in beneath it. This is already habit-hooks' architecture, so adopt
its taxonomy rather than inventing one.

### 7.2 Three tiers, composed per repo

| Tier | Scope | Contents |
|---|---|---|
| **0 — universal** | every repo, language-agnostic | gitleaks, osv-scanner, commitlint, jscpd (duplication), SBOM + provenance |
| **1 — per stack** | opt-in, one or more per repo | the verbs: `lint`, `typecheck`, `test`, `fix` |
| **2 — per repo** | local overrides | thresholds, snooze baseline, exclusions |

A single-package React app takes Tier 0 + `ts`. AutoApplicant takes Tier 0 + `ts` + `jvm`. Nothing
in Tier 0 knows either language exists.

### 7.3 Language coverage

Detector support as it stands upstream, against the stacks in scope:

| Stack | habit-hooks plugin | Detectors | Status |
|---|---|---|---|
| TypeScript / JS | ✅ `typescript` | eslint, knip, ts-morph | **pilot** |
| Python | ✅ `python` | ruff, deptry | ready |
| PHP | ✅ `php` | phpmd (bundled phar) | ready |
| Java | ✅ `java` | pmd | ready |
| Ruby | ✅ `ruby` | rubocop | n/a |
| *any* | ✅ `generic` | jscpd | duplication only |
| Kotlin | ❌ | detekt exists | **custom sensor** |
| C# | ❌ | Roslyn analyzers exist | custom sensor |
| Swift | ❌ | swiftlint exists | custom sensor |
| C++ | ❌ | clang-tidy exists | custom sensor |
| Rust / Go | ❌ | clippy / golangci-lint | custom sensor |

**Adding a language** = write a sensor that runs the existing detector and maps its rule IDs onto
smell names that already exist. It is not a rewrite. This is the concrete answer to "can I eventually
cover all of them": yes, one afternoon at a time, without the system growing a monolithic core.

### 7.4 A note on JVM feedback latency

Worth recording because it drove the pilot choice. Java's *linting* is fine — PMD is good. The
problem is the **build tool**: Gradle must resolve dependencies and compile before the worthwhile
rules can run at all (detekt and SpotBugs need a classpath), and JVM cold-start on a fresh runner
costs minutes even with caching, which is itself fiddly to configure in Actions. eslint and ruff
parse source directly and finish in seconds.

This barely matters in CI. It matters enormously **in-loop**, where the entire value proposition is
sub-5-second correction. Expect the JVM tier to run at pre-push and CI only, and to skip the in-loop
placement. That is a real asymmetry in the system, not a temporary gap.

---

## 8. Cost and the trust boundary

Two problems with one solution.

**The cost problem.** Running a model on every push is slow and metered. **The trust problem.**
A CI-side agent needs an API key *and* write access, on branches whose contents an agent authored —
the worst combination in the `pull_request_target` family of footguns.

**Resolution: pull the work to the local session instead of pushing the model into CI.**

```bash
gh pr checkout 123
gh pr view 123 --json title,body,comments
gh issue view 45
```

Context arrives locally, where the session is already paid for under a flat subscription. Result:

- **No API key ever enters CI.** The trust boundary collapses to nothing.
- **CI stays 100% deterministic** — fast, free, reproducible, and therefore actually trusted.
- Review happens at `/ship` time (§6) for your own work, and via `gh` import for anything else.

A CI-side agent triggered by a `/fix` comment remains *possible* later, but should be treated as an
optimisation to add if a real need appears — not part of v1.

---

## 9. Repository topology

Two repos. They have different consumers, different install mechanisms, and different release
cadences, which is what justifies the split.

```
C:\Users\akash\Projects\_foundry\        ← leading underscore: sorts above the IDE dirs,
  │                                          reads as "not an application"
  ├── foundry/                           → github.com/CMaintz/foundry
  │   ├── .github/workflows/             reusable workflow_call: tier0.yml, ts.yml, jvm.yml, php.yml
  │   ├── mise/                          shared task templates per stack
  │   ├── presets/                       eslint / tsconfig / ruff / phpstan base configs
  │   ├── habit-hooks/                   config.toml presets per stack
  │   ├── templates/                     project scaffolds
  │   ├── CONTRACT.md                    ◀── the verb interface (§3)
  │   └── DESIGN.md                      this document
  │
  └── cmaintz-skills/                    → github.com/CMaintz/cmaintz-skills
      ├── .claude-plugin/marketplace.json
      ├── skills/                        forked + own
      ├── hooks/                         habit-hooks wiring
      ├── agents/
      └── CONTRACT.md                    ◀── same file, kept in sync
```

- `foundry` is consumed **by repos**, via `uses: CMaintz/foundry/.github/workflows/ts.yml@v1`.
- `cmaintz-skills` is consumed **by the agent**, via `/plugin marketplace add CMaintz/cmaintz-skills`.

**The seam is `CONTRACT.md`** — the verb interface of §3, copied verbatim into both. As long as both
sides honour the verbs, they version independently without drifting. If that file ever needs to
differ between the two repos, the split was wrong and they should be merged.

---

## 10. Rollout

Vertical slices. Each phase ends with something demonstrably working end-to-end, rather than a layer
that is broad but unproven.

### Phase 1 — prove the loop on MDB

`WebstormProjects/MDB` — Vite + React 19, TS 5.7, eslint 9 flat config, already has `AGENTS.md`.
Chosen because it is a single package, and because **it has no test runner at all** — so we are
*adding* infrastructure rather than migrating it, which removes the largest source of incidental work.

1. `mise.toml` with the six verbs; pin node + TS.
2. Add vitest; set an honest initial coverage floor (whatever today's number is — a floor you can't
   meet is a floor you'll delete).
3. Add a `typecheck` verb — currently types are only checked as a side effect of `npm run build`.
4. `habit-hooks init`, TS plugin, **snooze the existing baseline immediately**.
5. Wire the in-loop hook. Confirm sub-5s.
6. Tier 0 + `ts` workflow in CI.
7. First `/ship` run, end to end.

**Exit criteria:** the same rule set demonstrably enforces the same thing in all three placements,
and one PR has gone through `/ship` without hand-holding.

### Phase 2 — fork and settle the skill library

Install all three sets; resolve the `code-review` collision; wire `learn` so that session learnings
start flowing into hooks. Run for ~2 weeks *without adding anything*, and keep a note of which skills
actually fire. That list is the input to Phase 4.

### Phase 3 — prove tier composition on AutoApplicant

The polyglot stress test: Kotlin/Gradle backend + Angular 17 frontend + an extension that has no
`package.json` at all. Also the place where existing drift gets resolved — eslint `^9.39.1` vs
`^9.22.0`, TS `^5.4.2` vs `~5.7.2`, two unrelated eslint configs. If Tier 0 + `ts` + `jvm` compose
cleanly here, the model is sound.

### Phase 4 — widen

Python and PHP tiers (both have upstream plugins, so this is configuration). Then a custom Kotlin
sensor wrapping detekt as the first proof that §7.3 works. Then write skills for the friction that
Phase 2 exposed — and delete the ones that never fired.

---

## 11. Open questions

### Resolved

| # | Question | Outcome |
|---|---|---|
| 1 | `mise` vs `just` on Windows | **`mise`.** Native Windows support confirmed; `mise run` works. Caveat found: `depends` runs prerequisites in parallel with no ordering guarantee, so `gate` uses a sequential `run` array instead. |
| 2 | Coverage floor policy | **Ratchet upward only.** Floor is set to today's measured number, may only rise. A floor you cannot meet is a floor you will delete. |
| 3 | `dist/` and `node_modules/` gitignored? | **Yes, correct already.** Zero tracked build output in MDB. No cleanup needed. |
| 5 | Public or private repos | **Public.** Marketplace install is far easier, and there is nothing sensitive here. |

### Still open

| # | Question | Blocks |
|---|---|---|
| 4 | Does the extension in AutoApplicant get a `package.json` (and enter the `ts` tier), or stay outside the gate? | Phase 3 |
| 6 | Which `code-review` binds to `/ship` step 4? | Phase 2 |
| 7 | MDB gitignores `/.claude/`. The in-loop hook is global for now — does it eventually become repo-local and committed? | Phase 4 |

### Lessons from Phase 1

Recorded because each one cost a red build or a wrong assumption:

- **Pin the tool, not just the action.** `jdx/mise-action` pinned by SHA still resolved mise itself from `mise.jdx.dev/VERSION`, which advertised `v2026.9.3` before that release's assets existed. Both mise jobs died in under 10s. Pin `version:` explicitly.
- **`contents: read` is not enough for gitleaks.** It lists the PR's commits and needs `pull-requests: read`.
- **jsdom is the dominant test cost.** Defaulting to `node` and opting in per file took MDB's suite from 20.0s to 2.6s. Do this in every new repo from the start.
- **habit-hooks caches.** ~25s cold, ~6s warm — which is what makes the `Stop`-hook placement viable. It is still far too slow for `PostToolUse`.
- **ESLint 9.24+ has the ratchet built in** (`--suppress-all`, `--prune-suppressions`). Do not hand-roll a baseline; do not disable rules.

---

## Appendix — references

- habit-hooks — <https://github.com/habit-hooks/habit-hooks>
- Matt Pocock's skills — <https://github.com/mattpocock/skills>
- Ivett Ördög's skills — <https://github.com/devill/ivetts-skills>
