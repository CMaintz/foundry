# Ticket schema - a ticket the `/feature` driver can work

The unit of work the `feature` driver (and `repo-align`) claims and drives to a PR:
a **GitHub Issue**. The driver normalizes it to one ticket object internally.

This file is reference: the `feature` skill inlines the fields it needs, so a
consumer repo need not copy it. Copy `ISSUE_TEMPLATE/agent-feature.yml` into the
consumer's `.github/ISSUE_TEMPLATE/` to enforce the schema on new issues.

The driver's output quality is capped by the ticket's. A ticket missing any
required field is not `agent:ready` - in puller mode it is skipped; in supervised
`/feature <ref>` mode the agent interviews to fill it first.

## Required fields

- **Intent** - the user story: what and why, in a sentence or two. This is what the
  fresh-context reviewer checks the diff against.
- **Acceptance criteria** - a **checklist** of `- [ ]` items, each verifiable and,
  where possible, machine-checkable. This is the load-bearing field: the driver's
  behavioural `verify` step and `ship`'s spec review both walk it item by item. No
  checklist, no claim.
- **Definition of Done** - a `- [ ]` checklist of ticket-specific done-conditions
  that are not behaviour, held to the same rule as the acceptance criteria: each
  item verifiable. It covers what this ticket needs and nothing in the standard
  pipeline does, so leave out anything the gate or `ship` already enforces (lint,
  tests passing, a conventional commit, a reviewed PR). "The migration has a
  working down step" belongs; "the gate is green" does not. When the acceptance
  criteria already say everything, write the sentinel
  `None beyond the acceptance criteria.` - that is a valid DoD. A ticket with no
  DoD section at all is not claimable: the puller skips it, supervised mode
  interviews for it.
- **Scope boundaries** - explicit "do not touch X". The guard against silent scope
  creep.
- **Pointers** - relevant files, modules, or prior art the agent should start from.

## Labels - the state machine

The driver moves a ticket through three labels; the issue thread is its work log.

- `agent:ready` - groomed, complete, free to claim. Applied only after the owner
  explicitly approves the full ticket, Definition of Done included.
- `agent:working` - claimed and assigned; exactly one at a time per session
  (WIP = 1), the session named by the ticket's latest `claimed by` comment.
- `agent:blocked` - escalated to a human, with the reason already posted to the
  thread.

## Onboarding - create the labels first

GitHub **silently drops** a template's `labels:` entry if the label does not exist
in the repo, so the state machine no-ops with no error until the labels exist. Run
[`scripts/setup-labels.sh`](../scripts/setup-labels.sh) once per repo (idempotent);
it creates these plus `align`, `ruleset-change`, and `autofix`. `foundry-init` runs
it for you.
