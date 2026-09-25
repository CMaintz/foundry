# Spec — Deterministic flake triager

**Status:** In progress · **Owner:** CMaintz · **Date:** 2026-09-19
**Home:** foundry (wrapper + baseline format + guard) · **Weight:** pre-push/CI

**Implemented & tested (in isolation):** `scripts/foundry-flaky` — `gate` mode
post-processes a test report (JUnit XML *and* vitest JSON) against `flaky-baseline.json`
and fails only if a NON-quarantined test failed (quarantined flakes are printed, never
hidden); `classify` mode reruns failed tests N times to separate flakes (flip) from real
failures (always fail) and surfaces prune candidates (quarantined-but-now-stable). Both
modes tested across formats + quarantined/real/no-baseline cases. `presets/baselines/flaky-baseline.example.json`
(schema); baseline reuses the guard's `snooze` kind — verified add=loosening (needs
label), remove=tightening (free), no new guard code. `mise/ts.toml` gains an opt-in
`test:flaky` integration task. **Not yet:** live rerun on a real runner (no JVM/node
project here — only the parsing/decision/classify logic is validated); Gradle `--tests`
rerun recipe wiring; auto-prune of stable entries (needs a green-streak counter — a
follow-on that can piggyback the loop-telemetry log).

## Problem

DESIGN §4.2 names three probabilistic roles; **Fixer and Reviewer are built, Triager
isn't.** A flaky test that fails the gate is worse than no test: it trains everyone —
human and agent — to ignore red, and it burns loop iterations chasing a ghost. The
deterministic 80% of triage (is this failure reproducible?) needs no model at all.

## Design

On a `test` failure, a wrapper does deterministic-first triage:

1. **Rerun only the failed tests, N times** (via runner filters — not the whole suite).
2. A test that **flips** (passes on rerun) is a flake candidate → recorded in a
   committed `flaky-baseline.json` (test id, first-seen ref, rerun evidence).
3. **Quarantined tests still run and still report, but don't gate.** This is done by
   **post-processing the runner's report** against the baseline in the wrapper — *not*
   by runner plugins or `@Disabled`. Don't fight the runner: let it run everything,
   then the wrapper computes the gating exit code = fail iff a *non-quarantined* test
   failed.
4. A quarantined test that passes **M consecutive** runs is **auto-pruned** (re-armed).

This keeps the oracle honest: a real, 100%-reproducible failure still fails the gate;
only genuinely non-deterministic tests are set aside, and only visibly.

## Per-stack wiring

### Java (deep)
- Parse `build/test-results/**/*.xml` (JUnit XML) → failed test ids.
- Rerun: `./gradlew :backend:test --tests <id>` × N.
- Gating decision: wrapper re-reads the XML, subtracts quarantined ids, sets exit.

### TypeScript (deep)
- vitest JSON reporter (`--reporter=json`) → failed test names.
- Rerun: `vitest run -t "<name>"` × N. (Use explicit reruns for *classification* —
  not vitest `--retry`, which silently hides flakes instead of recording them.)
- Same post-processing of the JSON report against the baseline.

### Other stacks (recipe)
- **PHP:** parse PHPUnit JUnit XML; rerun `--filter`. **Python:** pytest JUnit XML /
  `pytest-json-report`; rerun `-k`. **Kotlin/dotnet:** JUnit-XML / TRX, same shape.

## Ratchet mechanics

`flaky-baseline.json` **only shrinks**: entries are auto-pruned on sustained green, and
adding an entry is a loosening. Never regenerated wholesale to make a build pass.

## ruleset-guard changes

Watch `flaky-baseline.json`. Classifier:

| Change | Verdict |
|---|---|
| Entries only removed (auto-prune) | tightening — no label |
| Entry added (new quarantine) | loosening — needs `ruleset-change` (or a dedicated `flaky-quarantine`) label |

"This test is flaky, trust me" *should* be a deliberate, labelled human decision — the
guard makes it one.

## Placement

| Placement | Runs? | Why |
|---|---|---|
| In-loop | ❌ | rerun cost too high for the <30s Stop budget |
| Pre-push | ✅ | catches flakes before they hit CI |
| CI | ✅ | authoritative; quarantine keeps a known flake from blocking merge |

## If-funded tier

**Model Triager:** read stack traces to classify flaky-vs-real, dedupe repeat
failures, and auto-file a ticket that `/feature` can later pick up. Advisory only —
the deterministic rerun decides quarantine; the model just routes and explains.

## Acceptance criteria

1. A test injected to fail ~50% of the time is quarantined after N reruns and stops
   gating; it still appears in the report.
2. A test that fails 100% still fails the gate (never quarantined).
3. A quarantined test made stable is auto-pruned after M green runs.
4. Adding a quarantine entry without a label fails `ruleset-guard`; removing one passes.

## Backport split

- **foundry:** the rerun-and-classify wrapper, the baseline JSON format, per-stack
  report parsers, the `ruleset_guard.py` classifier.
- **consumer:** the baseline file contents (its own known flakes).
