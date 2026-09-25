# Spec — Local loop telemetry

**Status:** In progress · **Owner:** CMaintz · **Date:** 2026-09-19
**Home:** foundry (schema + wrapper) + cmaintz-skills (summarizer) · **Weight:** local-first

**Implemented & tested (in isolation):** `scripts/foundry-verb-wrap` — times a verb,
appends one JSONL line (`ts, ms, verb, scope, placement, exit, duration_ms`), always
propagates the verb's exit (telemetry failure can't change the outcome; validated across
success/fail/unwritable-path). `scripts/foundry-loop-report` — offline summariser: per-verb
time/fails/**regressions (thrash)**, time-sink, latest-red, placement/scope breakdown;
handles missing/empty/torn logs. Wired into `mise/ts.toml` + `mise/java.toml` (gate wraps
each verb; `FOUNDRY_TELEMETRY` + `scripts/` on PATH via `{{config_root}}`; array form kept
so the CONTRACT's sequential-not-`depends` rule holds). `foundry-init` vendors both scripts
+ gitignores `.foundry/`. `/loop-report` skill added to cmaintz-skills.
**Not yet:** end-to-end run on a live `mise` project (only the scripts are validated here —
no mise runtime in this env); smell-count emission from the habit-hooks Stop hook (the
smell-trend convergence signal — a follow-on); `gh run` CI mining lives in the skill.

## Problem

"Why did this run fail, is the loop converging or thrashing, where does the wall-clock
go, how many gate rounds to green" is invisible today. Thrash — the agent fixes the
in-loop-flagged smell, CI flags another, it regresses the first — is *felt*, never
*measured*. The `mise` verbs are the single chokepoint every placement runs through,
so the cheapest place to make the loop legible is right there.

## Design

**Emit:** a small portable-sh wrapper `foundry-verb-wrap <verb> -- <cmd…>` that each
of the six top-level verbs in a `mise` template is prefixed with. It runs the command,
times it, captures the exit code, and appends **one JSONL line** to a gitignored
`.foundry/telemetry.jsonl`:

```json
{"ts":"<iso>","verb":"lint","scope":"changed|whole","exit":0,
 "duration_ms":812,"placement":"hook|ship|ci|manual","smells":{"high-complexity":3}}
```

- **One wrapper, not per-task edits.** Wrapping only the six verb entry points (three
  extra characters of prefix per template) captures every invocation — direct,
  composed-via-`gate`, hook-driven — without touching leaf tasks. `smells` is
  populated by parsing habit-hooks' normalized JSON when it ran; omitted otherwise.
- **Placement** is inferred from env (`CI`, a hook-set `FOUNDRY_PLACEMENT`, else
  `manual`). `scope` reads whether `FOUNDRY_SINCE` was set (ties to the changed-scope
  spec).

**Summarize:** a `/loop-report` skill (cmaintz-skills) reads the JSONL and answers:
- **Convergence vs thrash** — is the per-smell count series monotonically falling, or
  oscillating? A smell that returns after being cleared is a thrash signal. This
  operationalises the "don't spin past two no-progress rounds" rule in `agent-loop.md`.
- **Time sinks** — wall-clock per verb, cold vs warm.
- **Rounds to green** — how many `gate` invocations from first-run to green.
- **CI mining (extension)** — `gh run list --json …` for CI job outcomes/durations
  (no repo instrumentation needed; answers "which job is the tall pole").

## Per-stack wiring

Schema, wrapper, and skill are **language-agnostic** (foundry / cmaintz-skills). Every
template just prefixes its verbs with the wrapper — identical for TS and Java. `smells`
parsing rides on habit-hooks' already-normalized output, so it's stack-independent.
Other stacks: same prefix, no per-stack code.

## Ratchet mechanics

None — telemetry is local observability, `.foundry/` is gitignored, nothing committed.
(Deliberately not a baseline: committing run traces would be noise and churn.)

## ruleset-guard changes

None (gitignored, non-source).

## Placement

| Placement | Emits? | Summarizer |
|---|---|---|
| In-loop | yes (via wrapper) | — |
| Pre-push | yes | `/loop-report` after `/ship` |
| CI | yes (local file discarded) + `gh run` mining | `/loop-report --ci` |

## If-funded tier

- **Token/cost accounting:** if a metered API is ever in the loop, log token counts per
  verb/round and correlate spend against convergence — "this refactor cost 40k tokens
  and 6 rounds." Aspirational; no spend today.
- **Hosted dashboard:** ship the JSONL to a sink for cross-session trends. Not needed
  while single-maintainer; the skill answers the same questions locally.

## Acceptance criteria

1. After a `/ship` run, `.foundry/telemetry.jsonl` has one line per verb invocation
   with a plausible `duration_ms` and correct `exit`.
2. `/loop-report` prints rounds-to-green and per-verb wall-clock for a real session.
3. When a fix→regress thrash is *induced* (clear a smell, reintroduce it), the report
   flags it as non-converging.
4. `/loop-report --ci` lists recent CI job durations via `gh run` with zero repo
   instrumentation.

## Backport split

- **foundry:** JSONL schema, `foundry-verb-wrap`, per-template prefix wiring,
  `.gitignore` entry.
- **cmaintz-skills:** the `/loop-report` summarizer skill.
- **consumer:** nothing beyond adopting the wrapper prefix (comes with the template).
