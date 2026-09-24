# layering-violation — a module reached across an architectural boundary

**What it's telling you.** Your architecture declares who may depend on whom (see the
layer map in the arch config). This import crosses a boundary the wrong way — e.g. the
domain reached into an adapter, or a use case imported a framework. Left alone, these
edges accumulate until the "layers" are decorative and nothing can be changed or tested
in isolation.

**Fix toward the dependency rule, not the symptom.**
- **Depend inward, never outward.** The core (domain/entities) must not know about the
  things that call it (adapters, controllers, frameworks). If the core "needs" an
  adapter, it actually needs an *interface* the core owns and the adapter implements —
  invert the dependency (a port).
- **Move the code, don't move the line.** If a class sits in the wrong layer for what it
  does, relocate it to the layer whose rules it obeys — don't keep it where it is and
  widen the layer map to allow the edge.
- **A framework leak in the core** means business logic is entangled with a library.
  Extract the pure logic; keep the framework call in the adapter/config layer.

**Don't game it.**
- Widening the layer map (adding the forbidden edge to `ALLOW`, or deleting a rule) to
  make the check pass is a **loosening** — it needs the `ruleset-change` label and a
  human, precisely because it silently redefines the architecture. That's the opposite
  of a fix.
- Casting to `any`/`Object`, importing via a string/dynamic path, or routing through a
  third module to dodge the detector hides the coupling instead of removing it — worse
  than the original violation.
- Adding the violation to the frozen baseline is only honest for *pre-existing* debt.
  New code that trips this rule should be fixed, not frozen.

The rule is a proxy for "each layer can be understood and replaced on its own." Clearing
it by weakening the rule defeats the purpose; clearing it by inverting the dependency is
the fix that makes the next change easier.
