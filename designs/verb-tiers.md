# Spec — Verb tiers & the six-verb decision

**Status:** Agreed (keep six + CONTRACT addendum) · **Owner:** CMaintz · **Date:** 2026-09-19
**Home:** foundry + cmaintz-skills (CONTRACT.md, kept identical)

## The decision

Keep the **six contract verbs frozen**; extend functionality *below* the contract, not
by growing it. The number matters as a *contract-stability* property — every caller may
assume exactly `fix/lint/typecheck/test/audit/gate` exist in every repo and never has to
ask — not as a limit on what the system can check.

## Three tiers

| Tier | What | Frozen? | New work goes here when… |
|---|---|---|---|
| **(a) Contract verbs** | the six | **yes** — a change is a major bump on both repos | (never grows in practice) |
| **(b) Verb composition** | what `lint`/`typecheck`/`test`/`audit`/`gate` *run* | no — repo-local | the concern fits an existing verb's meaning (arch → `lint`/`test`; flake → inside `test`) |
| **(c) Auxiliary tasks** | extra `mise` tasks (`novar`, `spotbugs`, `eval`, `setup:pmd`) | no — repo-local, non-contract | the concern isn't universal, or is deliberately advisory/report-only |

**The test a concern must pass to earn a seventh contract verb:** it must be
(1) *universal* — nearly every repo has real work for it — **and** (2) genuinely unable
to fit inside an existing verb. None of the five brainstorm features passes: arch fits
`lint`/`test`; prompt-eval isn't universal (only AI repos) and its deterministic tier is
already tests; flake is a `test` wrapper. The cost of a seventh contract verb is paid by
*all* repos (each must define it, even as a no-op) to serve a concern only *some* have.

Codified as the **Auxiliary tasks** section now added to CONTRACT.md (both copies).

## Disposition of AutoApplicant's current auxiliary tasks

Answering "should any of these hook into an existing verb?" — case by case:

- **`novar` → folded into `lint` (tier b). Done in foundry.** It *is* a lint rule; it
  lived outside `lint` only because whole-tree locally would fail on legacy `var`. It is
  **ratchet-scoped, not execute-scoped** — it diffs from `FOUNDRY_BASE_REF` (the ratchet
  base, default `origin/main`; CI sets the PR base SHA), *not* `FOUNDRY_SINCE` (the speed
  signal). So folding it into `lint` never fails on legacy `var` in any placement.
  Implemented in `mise/java.toml` (`lint = [spotlessCheck, novar]`) and the reusable
  `java.yml` (the separate `no-var` job and `no_var` input removed; the gate's lint step
  passes `FOUNDRY_BASE_REF`). A consumer inherits it by calling foundry's `java.yml` and
  folding `novar` into its own `mise.toml` `lint`; **AutoApplicant picks this up via its
  inline→foundry CI migration, a separate work-stream — not edited here.**
- **`spotbugs` → in AutoApplicant it is *already* blocking + ratcheted; its cleanup is
  folding into `audit`.** Correction to an earlier draft: AA does not run SpotBugs
  report-only. `quality.yml` runs `mise run backend:spotbugs` as a **blocking** job with
  a `config/spotbugs/exclude.xml` ratchet ("the current tree is clean"). So the general
  claim "report-only until ratcheted" is the right *default for a fresh repo*, but AA has
  already done the ratchet+tune. What remains for AA is purely a verb-tier tidy: fold
  `backend:spotbugs` into `backend:audit` (its semantic home — bug-pattern SAST) so it
  rides the gate composite instead of a standalone job. foundry's `java.yml` template
  keeps SpotBugs opt-in/report-only as the safe default for repos that haven't ratcheted.
- **`setup:pmd` → stays auxiliary (tier c).** It's provisioning (a `postinstall` hook),
  not a check. Never a verb member. **Keep as-is.**

## Acceptance

1. CONTRACT.md (both repos, identical) carries the Auxiliary-tasks section.
2. foundry `mise/java.toml` `lint` runs `novar` (ratchet-scoped via `FOUNDRY_BASE_REF`);
   the reusable `java.yml` no longer has a separate `no-var` job or `no_var` input, and
   its gate lint step passes `FOUNDRY_BASE_REF`. ✓ done.
3. `setup:pmd` stays auxiliary; `gate` does not run it. `spotbugs` stays opt-in in the
   foundry template; in AA it's blocking and slated to fold into `audit`.

## Backport split

- **foundry / cmaintz-skills:** the CONTRACT.md addendum (identical); the `novar`→`lint`
  fold in `mise/java.toml` + `java.yml`; `FOUNDRY_BASE_REF` convention.
- **consumer (AutoApplicant):** folding `novar` into its own `mise.toml` `lint` and the
  `spotbugs`→`audit` tidy — carried by the inline→foundry CI migration work-stream.
