# Foundry — dev-tooling / eval / observability / DX brainstorm

**Status:** Brainstorm (agreed to spec all five) · **Owner:** CMaintz · **Date:** 2026-09-19

High-leverage additions across dev tooling, evaluation, observability, developer
experience, and CI/CD. Five ideas, filtered against what already exists, then a
ranked value/effort shortlist.

> **Constraints note.** The original brainstorm was written under three constraints
> that have since been **relaxed** for the spec phase:
> - *Six frozen verbs* → new verbs are now allowed where they earn their place; the
>   existing structure may be edited to improve it.
> - *No API key in CI* → still the real-world default (no paid API/product spend),
>   but each idea may explore an optional "if-funded" tier as an aspirational note.
> - *Actions-minutes scarcity* → no longer a design constraint. Optimise for
>   end-product quality and how well the system produces good code, not minutes.
>
> The redundancy analysis below still holds and still governs the specs.

## Not proposed — already covered

Coupling/hotspot → `hotspot-rec`. Duplication → `jscpd`. Auto-fix on PR →
`autofix.yml`. Baseline-movement reporting → `ratchet-report.yml`. Ticket→PR →
`/feature`. Agent-done → green orchestration → `/ship` + `/feature` + the `gate-ok`
aggregate pattern (OVERVIEW §13). New work extends these where there's a real gap;
it does not re-skin them.

---

## 1. Architecture fitness functions

**Problem.** DESIGN.md and the CONTEXT/domain docs *describe* layering
(adapter→usecase, domain→framework-free) and forbid cycles, but nothing *enforces*
it. Layering violations and dependency cycles are structural at the module-graph
level — invisible to habit-hooks, which sees function-level smells — and they're the
ones that quietly rot a documented architecture into a big ball of mud.

**Fit.** The deterministic-oracle thesis applied to architecture: turn a documented
rule into a pass/fail exit code, per stack.
- TS → `dependency-cruiser` (or `madge` for cycles-only).
- Java → **ArchUnit**, which runs *as JUnit tests*.
- Python → `import-linter`.

**Ratchet, day one.** ArchUnit's `FreezingArchRule` (violation store that only
shrinks) and dependency-cruiser's `--ignore-known` baseline both retrofit without a
red day-one wall and only tighten. Rule configs join `ruleset-guard`'s watched set —
arch rules are the first thing an agent loosens to make a violation pass.

**Effort.** Medium. TS path is fast (parses source, good in-loop). Java path needs a
compiled classpath → CI/pre-push only, in-loop skipped (same JVM-latency asymmetry as
DESIGN §7.4).

---

## 2. Local loop telemetry — make the agent loop legible

**Problem.** "Why did this run fail, is the loop converging, where do time/tokens/CI
minutes go" is invisible. Thrash is felt, not measured — including the agent failure
mode of fix-flagged / CI-flags-other / regress-first, which is a convergence problem.

**Fit.** The `mise` verbs are the single chokepoint every placement runs through, so
instrument there: each verb appends one JSONL line (`{verb, exit, duration_ms,
smell_counts, ts}`) to a gitignored `.foundry/telemetry.jsonl`. A summarizer skill
answers: is smell-count monotonically falling (converging) or oscillating
(thrashing)? Which verb eats wall-clock? How many gate rounds to green? This turns
the "don't spin past two no-progress rounds" prose in `agent-loop.md` into something
measurable. Same summarizer can mine `gh run list --json` (free of minutes) for CI
outcomes/durations → one skill answers "is my loop converging" and "where do my CI
minutes go".

**Effort.** Low–Medium. Emit is trivial; value is in the summarizer's questions.

---

## 3. Prompt / agent-output regression eval

**Problem.** jobbuddy has an offline prompt-eval harness that dies in that repo. When
a prompt or output-shaping change lands, nothing catches a silent quality
regression — the one class of change the deterministic gate is blind to.

**Fit (split per DESIGN §4).**
- **Deterministic assertions gate** — valid JSON / schema match / required fields /
  regex. Reproducible, no model. Maps into `test` (or a dedicated verb — see specs).
- **LLM-judged scoring is Reviewer-class — advisory, never blocking.** Runs
  local/pre-push (API key); emits a score delta as a PR comment. CI replays recorded
  fixtures and re-runs the deterministic assertions only.
- **Ratchet:** a committed score baseline that may only rise; joins `ruleset-guard`.

**Effort.** Medium–High; most consumer-specific. Worth it because jobbuddy proved the
shape — the work is generalizing, not inventing.

---

## 4. Changed-scope gate — make the loop fast

**Problem.** `/ship` + `/feature` + `gate-ok` already close most of the agent-done →
green gap. What's left is **gate speed**: in-loop/pre-push run the full gate over the
whole tree, so the agent waits and does fewer iterations per unit time. Slow feedback
*is* the DX gap now.

**Fit.** The *same* rule set, scoped by placement: a `--since <ref>` scope so
in-loop/pre-push run lint+typecheck+test over the changeset (merge-base diff) while CI
stays whole-tree authoritative. OVERVIEW §12 already does this once (in-loop scope is
`--branch`); generalize it into every `mise` template.

**Effort.** Low–Medium per stack; compounds on every future loop iteration.

---

## 5. Deterministic flake triager

**Problem.** DESIGN §4.2 names three probabilistic roles; Fixer and Reviewer are
built, **Triager isn't.** A flaky test failing the gate is worse than no test — it
trains everyone to ignore red and burns iterations chasing a ghost.

**Fit.** Do the deterministic 80% without a model: on a `test` failure, re-run the
failed tests N times; a test that flips is quarantined into a committed
`flaky-baseline.json` (ratchet: only shrinks; a 20-green quarantined test is pruned
and re-armed). Quarantined tests still run and report but don't gate. The baseline
joins `ruleset-guard` — adding a flaky exemption is a deliberate, labelled decision.
Model Triager (dedupe, route-to-ticket) is a later advisory add.

**Effort.** Medium. Re-run-and-classify is a wrapper around `mise run test`; per-stack
test selection reuses #4's plumbing.

---

## Shortlist — ranked by value/effort

| # | Idea | Value/Effort | Home | Shift-left? |
|---|---|---|---|---|
| **1** | **Changed-scope gate** (`--since`) | Highest — compounds on every loop | foundry (per-`mise` template) | ✅ pure local |
| **2** | **Local loop telemetry** + `gh run` mining | High — observability, feeds convergence | foundry (schema+skill); consumer emits | ✅ local-first |
| **3** | **Architecture fitness functions** | High — flagship document→enforce | foundry (presets+wiring); consumer picks layers | ⚖️ TS in-loop, JVM pre-push/CI |
| **4** | **Deterministic flake triager** | Medium — fills a named gap | foundry (wrapper); consumer owns baseline | ✅ pre-push |
| **5** | **Prompt/agent-output eval** | Medium — biggest new capability, most consumer-specific | consumer (jobbuddy) → generalize to foundry | ✅ local; CI replays only |

**Sequencing:** #1 and #2 first (fast + legible loop is the real DX gap once `/ship`
and `/feature` exist). #3 designed now (layer names are the hard part, already
half-written in the docs), built next. #4 and #5 follow.
