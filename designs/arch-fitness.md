# Spec — Architecture fitness functions

**Status:** In progress · **Owner:** CMaintz · **Date:** 2026-09-19
**Home:** foundry (rule templates + presets + guard) · **Weight:** ⚖️ TS in-loop, JVM pre-push/CI

**Implemented:** `presets/arch/dependency-cruiser.cjs` — generic, architecture-agnostic
layer+cycle rules generated from an editable `LAYERS`/`ALLOW` map (executed here: rule
generation verified for hexagonal + modular maps); `presets/arch/ArchitectureTest.java`
— ArchUnit template (layered + framework-freedom + cycles, wrapped in `FreezingArchRule`);
`presets/arch/guides/{layering-violation,dependency-cycle}.md`; `ruleset_guard.py` gains
a `lines` kind for the ArchUnit freeze store (tested; dep-cruiser baseline reuses `snooze`);
`mise/ts.toml` adds an opt-in `arch` task. **Not yet:** live ArchUnit/dep-cruiser run on a
real project (no JVM/node project here); Python `.importlinter` preset; foundry-init
vendoring of the arch presets.

## Problem

AutoApplicant's backend is textbook hexagonal — `adapter/ port/ usecase/ domain/
config/` — and the docs *state* the rules (domain is framework-free, usecase must not
reach into adapter, no dependency cycles). Nothing *enforces* them. These are
module-graph-level structural properties, invisible to habit-hooks (which sees
function-level smells), and they're precisely what rots a documented architecture into
a big ball of mud one "just this once" import at a time. Neither ArchUnit nor
dependency-cruiser is present in AutoApplicant today — this is genuinely unbuilt.

## Design

Deterministic architecture rules, **folded into existing verbs** (tier-(b) verb
composition — no new contract verb; see the verb-tiers note):

- **Java → ArchUnit**, expressed as JUnit tests → runs under `test`.
- **TS → dependency-cruiser** (cycles + forbidden cross-layer imports) → under `lint`.
- **Python → import-linter** → under `lint`.

The placement asymmetry (arch-as-test on Java, arch-as-lint on TS) is invisible to
callers, who only ever call verbs — the verb interface earning its keep exactly as
CONTRACT.md intends.

### Architecture-agnostic by construction

The mechanism is **not hexagonal-specific** — hexagonal is one preset. A consumer
describes *their* architecture as a small model and every rule is generated from it:

- **LAYERS** — a name → path/package pattern map (what code belongs to each layer).
- **ALLOW** — per layer, which other layers it may import; anything else is forbidden.
- **no cycles** — always enforced.
- **framework-freedom** — optional "layer X must not import package regex Y".

foundry ships this as an editable preset per stack (`presets/arch/`), plus **coaching
guides** (`presets/arch/guides/{layering-violation,dependency-cycle}.md`) that render on
failure. The consumer fills the map; the layer *names* and edges are theirs.

Four worked example maps ship in the presets (swap one in, or write your own):
- **Hexagonal / ports-and-adapters** (AutoApplicant): domain ← port ← usecase ← adapter/config; domain framework-free.
- **Classic layered (n-tier):** web → service → data, one direction only.
- **Clean / onion:** entities ← usecases ← interfaces ← frameworks.
- **Modular / feature-sliced:** each feature may import only a shared kernel, never another feature (module isolation).

AutoApplicant's hexagonal rule set is just the default instance:
- `domain` imports no other layer (no Spring, no `adapter`, no `usecase`); `usecase` →
  `domain`+`port`, never `adapter`; `adapter` implements `port`; no package cycles.

## Per-stack wiring

### Java (deep)
- Add an **ArchUnit test source set / package `…/arch/`** so the rules live in their
  own place and are *always run* — changed-scope test selection (see changed-scope
  spec) must never silently skip them (they're cheap and global). Wire into
  `backend:test` (or a `backend:arch` auxiliary task that `test` depends on).
- Ratchet via `FreezingArchRule` backed by a committed violation store directory
  (verify the exact store path/API at implementation — do not hard-code here).

### TypeScript (deep)
- `.dependency-cruiser.js` with `forbidden` rules for cycles + layer boundaries, run in
  `lint`. Known pre-existing violations recorded in dependency-cruiser's
  known-violations baseline (verify the exact `--ignore-known` flag/file at impl).

### Other stacks (recipe)
- **Python:** `.importlinter` contracts (layers/forbidden); run in `lint`.
- **Kotlin:** Konsist or ArchUnit-for-Kotlin, as `test`. **PHP:** deptry/phpat as
  `lint`. **dotnet:** NetArchTest as `test`.

## Ratchet mechanics

- **Java:** `FreezingArchRule` violation store — existing violations frozen, store may
  **only shrink**. Retrofits onto a dirty codebase without a red day-one wall.
- **TS:** dependency-cruiser known-violations baseline — same shrink-only property.
- Both are committed baseline files, same doctrine as eslint-suppressions/snooze.

## ruleset-guard changes

Two mechanisms, matching what each artifact is:

| Artifact | Guard mechanism | Loosening (needs `ruleset-change`) |
|---|---|---|
| ArchUnit freeze store (`archunit_store/*.txt`) | **`lines` kind** (new; multiset of frozen-violation lines) — done | a store file gains a line |
| dep-cruiser known-violations (`.dependency-cruiser-known-violations.json`) | existing **`snooze`** kind (value_counts over the JSON) | a violation added |
| rule config (`.dependency-cruiser.cjs`, ArchUnit rule classes, `.importlinter`) | existing **ruleset-file watch** (any change + source ⇒ label) | `ALLOW` widened / a rule removed |

The count classifiers catch *baseline* growth; the ruleset-file watch catches *rule*
weakening (widening `ALLOW`, deleting a rule), which isn't count-based — it rides the
existing "touched a ruleset file + source ⇒ needs a human label" control.

## Placement

| Placement | TS (dep-cruiser) | Java (ArchUnit) |
|---|---|---|
| In-loop | ✅ fast (parses source) | ❌ needs compiled classpath (JVM asymmetry, DESIGN §7.4) |
| Pre-push | ✅ | ✅ |
| CI | ✅ | ✅ |

## If-funded tier

None — fully deterministic. That's a *strength*: architecture enforcement never needs
a model, so it's pure oracle.

## Acceptance criteria

1. A PR making `domain` import Spring fails `test` (Java) / `lint` (TS).
2. An existing violation recorded in the frozen store does **not** fail the gate.
3. Removing a violation + pruning the store passes `ruleset-guard` **without** a label.
4. Adding a new forbidden cross-layer import fails, with a coaching guide printed.
5. Introducing a package cycle fails.

## Backport split

- **foundry:** rule templates, starter configs, coaching guides, the three
  `ruleset_guard.py` classifiers, per-template verb wiring.
- **consumer:** the layer→folder map and which rules are enabled (AutoApplicant is the
  reference; its hexagonal map ships as the worked example).
