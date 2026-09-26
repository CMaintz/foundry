# Spec — Prompt / agent-output regression eval

**Status:** In progress · **Owner:** CMaintz · **Date:** 2026-09-19
**Home:** consumer (AutoApplicant) → generalize to foundry · **Weight:** local; CI replays only

**Implemented:** `presets/prompt-eval/` — a reusable harness generalising AutoApplicant's
`PromptEvalHarnessTest`: `prompt-eval.test.ts` (vitest) + `PromptEvalHarnessTest.java`
(JUnit `@TestFactory`) apply the **ranking** assertions (good ≥ FLOOR, weak ≤ CEILING,
gap ≥ SEPARATION) + optional prompt-block checks against a *consumer-supplied* scorer
(foundry ships no scorer). `fixtures/example.json` + `manifest.json` (the ratcheted
surface). `ruleset_guard.py` gains a **`coverage` kind** — INVERSE of a debt baseline:
removing a fixture = loosening (needs label), adding = free; tested (comment edits don't
false-flag). Ranking logic verified with a toy scorer. Runs under `test` (fixtures are
tests — no verb change). **Scope note:** narrowest of the five — only AI-output repos need
it; this is a clean backport of AA's proven pattern so future AI repos inherit it.
**Not yet:** the consumer half (AA keeps its `DocumentQualityEvaluator` + real fixtures;
wiring the generalised template back into AA is follow-on); the if-funded LLM-judge tier
(documented below, needs an API key — not built, no spend).

## Problem

Prompt or output-shaping changes can silently regress quality — the one class of
change the deterministic gate is blind to, because the output is probabilistic.
AutoApplicant **already solves this offline and deterministically**:
`PromptEvalHarnessTest` scores fixtures with `DocumentQualityEvaluator` (a
model-free scorer) and asserts on the *ranking* of good vs weak samples, plus asserts
the composed prompt carries the blocks it must. The task is to **generalize the
pattern into foundry** — not rewrite the scorer, which is domain-specific and stays in
the consumer.

## Design

The generalizable contract, distilled from what the real harness asserts:

- **Fixtures** — JSON `(input context, good sample, weak sample)` in a resources dir.
- **A repo-provided deterministic scorer** — stays in the consumer
  (`DocumentQualityEvaluator` is AutoApplicant's, not foundry's).
- **Ranking assertions** (the trustworthy signal): `good ≥ FLOOR`, `weak ≤ CEILING`,
  and `good − weak ≥ MIN_SEPARATION`. Absolute cutoffs on hand-written samples are
  arbitrary; *separation* is what makes a scorer trustworthy as a regression metric.
- **Structural prompt assertions** — the composed prompt contains required blocks
  (e.g. language directive, banned-phrases section, market conventions). Catches a
  prompt regression at composition time, not weeks later in a bad output.
- **Runs offline, as ordinary tests → under `test`.** No new contract verb: prompt-eval
  fails the universality test (only AI-output repos have this work), so it lives in
  `test` for the deterministic tier, with an optional auxiliary `eval` task (tier-(c))
  for the funded LLM-judge tier.

foundry ships: the fixture schema, harness templates (JUnit `@TestFactory` for Java,
`describe.each`/`it.each` for TS-vitest), and the floor/ceiling/separation assertion
helpers. The scorer and fixtures are the consumer's.

## Per-stack wiring

### Java (deep)
- Generalize AutoApplicant's `PromptEvalHarnessTest` shape into a foundry template: a
  `@TestFactory` that loads fixtures from `src/test/resources/prompt-eval/` and applies
  the ranking + structural assertions against a repo-supplied `QualityScorer` interface.
  Already under `backend:test` — zero verb change.

### TypeScript (deep)
- vitest template: `it.each(fixtures)` applying the same ranking assertions against a
  repo-supplied scorer function; fixtures as JSON alongside the test. Under `test`.

### Other stacks (recipe)
- **Python:** pytest `@pytest.mark.parametrize` over fixture files; scorer is a repo
  function. **PHP:** PHPUnit data provider. Same three assertions, same fixture schema.

## Ratchet mechanics

**Ratchet the fixture *count*, not the scores.** Scores are not monotone, and
ratcheting them upward invites overfitting to the scorer — the exact game-the-proxy
failure `agent-loop.md` warns against. Instead: the **fixture set may only grow** (you
never delete a regression case), and the FLOOR/CEILING/SEPARATION thresholds are
*ruleset* (guarded), not a ratchet.

## ruleset-guard changes

Watch the fixtures dir + the threshold constants. Classifier:

| Change | Verdict |
|---|---|
| Fixture added | tightening (more coverage) — no label |
| Fixture removed | loosening — needs label |
| `FLOOR`↓ / `CEILING`↑ / `SEPARATION`↓ | loosening — needs label |

## Placement

| Placement | Deterministic tier | LLM-judge tier |
|---|---|---|
| In-loop | ✅ (offline, just tests) | — |
| Pre-push | ✅ | (if funded) advisory PR comment |
| CI | ✅ replays recorded fixtures + re-runs assertions | ❌ never calls a model |

## If-funded tier

- **LLM-judge on real generations:** run the app's generation path, feed the output to
  *both* the deterministic scorer and a judge model; post a score-delta comment.
  Reviewer-class — **advisory, never blocks** (DESIGN §4.2).
- **Fixture mining:** use the judge to propose new fixtures from production near-misses,
  growing the (ratcheted) fixture set.
- No spend today; the deterministic tier is the whole real-world deliverable.

## Acceptance criteria

1. A prompt change that drops a required block fails `test` at composition time.
2. A scorer that can't separate good from weak fails the separation assertion.
3. Adding a fixture passes `ruleset-guard`; lowering `FLOOR` needs a label.
4. The generalized template runs in a TS/vitest repo as well as in AutoApplicant/JUnit,
   proving it's a foundry pattern and not an AutoApplicant one-off.

## Backport split

- **foundry:** fixture schema, JUnit + vitest harness templates, assertion helpers, the
  `ruleset_guard.py` classifier, the `QualityScorer` interface shape.
- **consumer:** the scorer implementation (`DocumentQualityEvaluator`), the fixtures,
  and the threshold values.
