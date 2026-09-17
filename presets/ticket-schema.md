# Ticket schema — a ticket the `/feature` driver can work

The unit of work the `feature` driver claims and drives to a PR. One schema, two
transports: a **GitHub Issue** (the default) or a local `tickets/*.md` frontmatter
block (the fallback for repos with no GitHub remote). Both normalize to the same
object inside the driver.

This file is reference: the `feature` skill inlines the fields it needs, so a
consumer repo need not copy it. Copy it in only if you use the local-md fallback
and want the frontmatter format to hand — and copy `ISSUE_TEMPLATE/agent-feature.yml`
into the consumer's `.github/ISSUE_TEMPLATE/` if you use the GitHub transport.

The driver's output quality is capped by the ticket's. A ticket missing any
required field is not `agent:ready` — in puller mode it is skipped; in supervised
`/feature <ref>` mode the agent interviews to fill it first.

## Required fields

- **Intent** — the user story: what and why, in a sentence or two. This is what the
  fresh-context reviewer checks the diff against.
- **Acceptance criteria** — a **checklist** of `- [ ]` items, each verifiable and,
  where possible, machine-checkable. This is the load-bearing field: the driver's
  behavioural `verify` step and `ship`'s spec review both walk it item by item. No
  checklist, no claim.
- **Scope boundaries** — explicit "do not touch X". The guard against silent scope
  creep.
- **Pointers** — relevant files, modules, or prior art the agent should start from.

## Labels — the state machine (GitHub transport)

The driver moves a ticket through three labels; the issue thread is its work log.

- `agent:ready` — groomed, complete, free to claim.
- `agent:working` — claimed and assigned; exactly one at a time per worker (WIP = 1).
- `agent:blocked` — escalated to a human, with the reason already posted to the
  thread.

## Onboarding — create the labels first

GitHub **silently drops** a template's `labels:` entry if the label does not exist
in the repo, so the state machine no-ops with no error until the labels exist.
Create them once per consumer repo:

```bash
gh label create agent:ready   --color 0e8a16 --description "Groomed, complete, free to claim"
gh label create agent:working --color fbca04 --description "Claimed and assigned (WIP=1)"
gh label create agent:blocked --color d93f0b --description "Escalated to a human; reason in thread"
```

## Local-md transport

For a repo with no GitHub remote, a ticket is `tickets/<slug>.md` with the same
fields as frontmatter, plus two the labels carry on GitHub:

```yaml
---
status: ready        # ready | working | blocked
claimed_at:          # ISO timestamp, stamped on claim — drives the 30-min stale reset
intent: >
  As a <role> I want <capability> so that <benefit>.
scope: >
  Do not touch <X>.
pointers:
  - src/foo/bar.ts
---

## Acceptance criteria
- [ ] ...
- [ ] ...
```

`claimed_at` exists because local files carry no GitHub assignment timestamp, and
the stale-claim reset needs one.
