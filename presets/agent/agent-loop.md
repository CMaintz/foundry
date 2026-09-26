# The loop — how you converge on "done"

Copy the relevant lines into your repo's `AGENTS.md` / `CLAUDE.md`, or `@`-include
this file. Language-agnostic. This is the *working loop* every change runs through;
`code-standards.md` is what "good" looks like, this is how you get there.

## The one idea

You are in a loop with a **deterministic oracle**. The oracle (`mise run gate`,
plus the Stop hook's smell coaching) decides *done*; you propose. Run it, read the
feedback, fix the real cause, run it again — until it's green **and** the change is
genuinely right. **"Done" is a green exit code from a clean tree, never your own
say-so.** A claim that you fixed something is not evidence; the oracle is.

## The inner loop (every change)

1. **Observe.** Run the oracle. Read the *specific* feedback — the failing verb, the
   named smell and its guide — not just "it failed."
2. **Diagnose.** A failure/smell is a *symptom*. Fix the thing it points at (the
   missing abstraction, the actual bug), not the symptom. If you can't name the
   cause, you're not ready to fix it — investigate first (fan out a sub-agent to
   read the surrounding code).
3. **Act.** The smallest change that addresses the cause.
4. **Verify.** Re-run the oracle from a clean tree. Then self-check: *could I defend
   this as one genuine fix, or is it a dodge?* If it's a dodge, it isn't done.
5. **Repeat** until green **and** honest.

## Done, and when to stop

- **Done** = oracle green from a clean tree **and** the change genuinely right.
- **Stop and surface** — don't "win" by weakening the gate. If you cannot go green
  without disabling a check, lowering a threshold, or growing a baseline, that's a
  deliberate, labelled human decision (`ruleset-guard`), not a fix. Say so and stop.
- **Don't spin.** If two rounds make no real progress, or the only remaining path is
  to weaken a rule, stop and report what's blocking — looping past that wastes work.

## Tiered loops — cheap and often, expensive and rare

The same rule set runs at three cadences, so a failure surfaces as early (cheap) as
possible — trust the in-loop signal, don't defer to CI:

- **In-loop** (Stop hook, every turn): format, types, structural smells.
- **Pre-push** (`/ship`, git pre-push): the full `mise run gate`.
- **CI** (per PR): the same gate + guards.

Same rules in each — no "passes locally, fails in CI."

### Fast iterative runs — `FOUNDRY_SINCE`

While you're *iterating* — running the oracle over and over on one change — scope the
file-local verbs to what you touched so each round is fast. Set `FOUNDRY_SINCE` to your
branch base:

```
FOUNDRY_SINCE=origin/main mise run gate    # lint + test only over the changeset
```

`lint` and `test` then run on changed files only (tests via the module graph);
`typecheck` still runs whole-tree, because a change can break an unchanged file's types
and scoping that would be a false green. **Your final verification is always a clean,
whole-tree `mise run gate` with `FOUNDRY_SINCE` unset** — the scoped runs are for speed
during the loop, not for declaring done. CI never sets it, so whole-tree CI stays the
backstop. Unset it and you're back to the full local gate; an unresolvable ref falls
back to whole-tree on its own.

## Outer loop — campaigns (`repo-align`)

Paying down debt is the same discipline, scaled — but **bounded**: pick a target up
front (one file, one module, a small related surface), then pick a slice → inner
loop → **adversarially review** the fix → ship → prune → repeat until *that target*
is clean, no safe slice remains in it, or a guardrail trips. Stop there; don't grind
the whole repo baseline in one run.

## Never game the metric

Every check is a *proxy* for "code that's safe to change." A change that satisfies
the proxy while defeating its purpose — split at line 200, `any`-cast, a 5-parameter
helper, snooze-to-pass — is **worse** than the smell it clears, because it hides it.
The coaching argues against mechanical compliance on purpose; the deep fix is the
one that makes the next change easier, not the one that flips the counter.
