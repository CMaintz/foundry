# Design — the backlog-driven feature driver (`/feature`)

A ticket-in, PR-out driver that lets an agent pick up a feature request and grind
it to the repo's baseline — lint, types, tests, coverage, static analysis — with
no human in the inner loop, then hand a reviewable PR back.

This document is the spec. For the system it builds on, read
[OVERVIEW.md](../OVERVIEW.md); for the verb interface it depends on,
[CONTRACT.md](../CONTRACT.md).

---

## 1. The one idea

Foundry already answers *"when is a change done?"* — a green `mise run gate` from
a clean tree, nothing else. What it does **not** yet provide is the thing in
front of that: a way to turn a *feature request* into a change that reaches a
green gate on its own, and to do it repeatably across a backlog.

So the driver is deliberately thin. It does **not** re-implement standards,
looping, or review — those are the gate, the ratchets, and `/ship`. It supplies
only the two missing halves:

1. **Intake** — a feature request becomes a well-formed, agent-readable ticket.
2. **A driver** — ticket → worktree → implement → *inner gate-fix loop* → hand to
   `/ship`.

The loop's terminating condition is borrowed, not invented: **the gate is the
oracle; the driver is bounded persistence toward it; `/ship` is the trusted
handoff.** An agent's claim that it's done is never evidence — the exit code is.

## 2. Why foundry is the base, not a bolt-on

Everything hard about "loop until the repo's standards are met" is already solved
here, and re-solving it elsewhere would just drift:

| The hard part | Foundry's existing answer |
|---|---|
| A single machine-checkable "definition of done" | `mise run gate` (lint → typecheck → test+coverage → audit), one exit code |
| Polyglot — works on any project | callers invoke the six **verbs**, never tools |
| The loop gaming the gate (`// eslint-disable`, split-a-file) | `ruleset-guard` (loosening needs a human label) + habit-hooks anti-gaming coaching |
| Trustworthy handoff (commit, review, PR) | `/ship`: re-gate → fresh-context review vs the linked issue → conventional commit → PR |
| Correctness a linter can't see | `/ship`'s fresh-context reviewer (Standards + Spec lenses) |

The driver consumes all of this. If a capability it needs isn't language-specific,
it belongs in foundry (per FEATURES backport discipline), not in the driver.

## 3. Artifacts and placement (respect the two-repo split)

Per [CONTRACT.md](../CONTRACT.md), skills live in `cmaintz-skills`, CI-half and
preset artifacts in `foundry`. So:

| Artifact | Repo | Path |
|---|---|---|
| The `/feature` driver skill | `cmaintz-skills` | `skills/feature/SKILL.md` (+ helpers) |
| GitHub issue template | `foundry` | `presets/ISSUE_TEMPLATE/agent-feature.yml` |
| Ticket schema (reference) | `foundry` | `presets/ticket-schema.md` |
| Inventory entry | `foundry` | `FEATURES.md` (same session) |

Adding a skill is **additive** under CONTRACT versioning — no major bump.

## 4. The ticket is the spec (and caps output quality)

A GitHub Issue body normalizes to **one ticket object** inside the driver.

Required fields:

- **Intent** — the user story / what and why.
- **Acceptance criteria** — a **checklist** (`- [ ]` items), each ideally
  machine-checkable. This is the single artifact both `/ship`'s spec-lens reviewer
  and the behavioural `verify` step walk **item-by-item**. Without a checklist a
  ticket is not `agent:ready` — "verify against acceptance criteria" is otherwise
  vibes.
- **Scope boundaries** — explicit "do not touch X"; the guard against silent
  scope creep.
- **Pointers** — relevant files / modules / prior art.

The template exists to force these. A good ticket makes the downstream spec review
and behavioural verify *sharper for free*.

## 5. State machine

Labels are the state; the issue thread is the durable work log.

```
             claim (atomic)          gate green + verify + ship
 agent:ready ───────────────▶ agent:working ───────────────────▶ (PR open, label cleared)
      ▲                            │
      │ 30-min stale reset         │ inner-loop exhausted / no-progress
      │ (working, no branch/PR)    ▼
      └──────────────────────  agent:blocked  (stuck-state posted to thread)
```

- `agent:ready` — groomed, has a checklist, free to claim.
- `agent:working` — claimed and assigned; exactly one at a time (WIP = 1).
- `agent:blocked` — escalated to a human, with the reason already in the thread.

## 6. The driver flow

```
puller (loop skill, interval)
  └─ claim next agent:ready ticket ──▶ agent:working   (atomic, WIP = 1)
       └─ worktree off origin/main   (collaboration.md: own branch, 1 → 1 PR)
            └─ normalize ticket; if criteria thin → interview to fill template
                 └─ INNER LOOP  (see §8): implement → `mise run gate`
                      ├─ green ──▶ verify (behavioural, vs acceptance checklist)
                      │              └─ /ship  (re-gate → fresh-context review → commit → PR)
                      └─ red   ──▶ apply fix + habit-hooks coaching → retry
                                   ⊗ exhausted / no-progress → escalate (§8)
```

The driver owns only the **front half** (claim → worktree → implement → inner
loop → verify). The moment the tree is green and behaviourally verified, `/ship`
owns the rest. The driver never opens a PR itself — that keeps one trusted path
to `main`.

## 7. Claim protocol — the hard part of semi-auto

Semi-auto's failure modes are all about the claim. The spec is deliberately
strict:

- **Atomic claim.** Flip `agent:ready` → `agent:working` **and assign** *before*
  any code is written. Never pick a ticket already `agent:working`. On GitHub this
  is a labelled+assigned edit; a claim that loses a race (label already moved) is
  abandoned, not forced.
- **WIP limit = 1** to start. One in-flight ticket per machine. Raise only after
  the loop has earned trust.
- **Worktree per ticket.** Each claim gets its own worktree off `origin/main`, so
  the loop honours `collaboration.md` (own branch off `origin/main`, one branch →
  one PR) without touching the main checkout. Removed on success or abandon.
- **Stale-claim recovery.** A ticket `agent:working` with **no branch and no PR**
  for **30 minutes** resets to `agent:ready`. Without this, one crashed session
  strands a ticket forever. (Threshold tunable; 30 min is the starting default.)

## 8. Inner-loop bounds — so "loop until solved" actually terminates

The gate defines *done*; the driver must define *give up*.

- **Max 5 gate-fix cycles.** implement/fix → `mise run gate` → parse failures +
  habit-hooks coaching → fix → repeat, at most 5 times.
- **No-progress exit.** If the **same failure set** appears two cycles running,
  escalate *immediately* — this catches thrashing at cycle 2 instead of burning
  all 5 on a wall.
- **Durable escalation.** On exhaustion or no-progress: **post the stuck-state to
  the issue thread first** (what was tried, the failing verbs, the last gate
  output), **then** flip to `agent:blocked`. An in-session explanation dies with
  the session; the thread is the memory.
- **Anti-gaming is inherited, not re-added.** The loop physically cannot "win" by
  loosening a rule — `ruleset-guard` blocks a source+ruleset PR without a human
  label, and habit-hooks coaching argues against mechanical compliance. The driver
  relies on this rather than policing it.

## 9. Behavioural verify + spec review

Green ≠ correct. Two checks stand between a green gate and a PR:

- **Behavioural `verify`** — runs the app / feature against each acceptance-criteria
  item. The gate proves the code is *clean*; verify proves it *does the thing*.
  This is why the checklist format in §4 is load-bearing.
- **Spec review** — handled inside `/ship`'s fresh-context reviewer, which sees
  only the diff and the linked issue, never the conversation that wrote the code.

## 10. Rollout — dogfood before the puller (exercise-gate-changes)

The puller is a *thin wrapper* over the driver, so building both costs little —
but the loop is not turned on until the driver is proven:

1. Build the driver **and** the puller wrapper.
2. **Prove the driver supervised on one real ticket** — invoke `/feature <id>`
   by hand, watch the inner loop, land the PR. This is the "never ship a
   gate/config change without running it" rule applied to the driver itself.
3. Only then enable the backlog puller on the `loop` interval.

This honours the signed-off semi-auto goal without shipping an unexercised loop.

## 11. v1 scope, non-goals, open questions

**In scope (v1):** GitHub Issues as the transport; WIP = 1; 30-min stale reset;
5-cycle + no-progress inner loop; supervised dogfood then puller.

**Non-goals (v1):** multi-ticket parallelism; a bespoke tracker integration
(Linear/Jira); a no-GitHub / local-file transport; auto-merging PRs (a human still
approves).

**Open questions:**
- Orchestration substrate for the puller — the `loop` skill (self-paced) vs a
  deterministic `Workflow` script (needed only if we later fan out candidate
  approaches → judge → implement). `loop` is enough for v1.
- How `/feature` interviews for a thin ticket without blocking an unattended
  puller run (probably: puller only claims tickets that already pass a
  criteria-completeness check; interview mode is for supervised `/feature <id>`).
