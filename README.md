# foundry

Reusable CI workflows, `mise` task templates and config presets behind a single six-verb interface, so the same rule set runs while an agent edits, before you push, and on the PR.

Companion repo: **[cmaintz-skills](https://github.com/CMaintz/cmaintz-skills)** — the agent half (skills, hooks). The seam between them is [CONTRACT.md](./CONTRACT.md), which is copied verbatim into both.

> **New here? Read [OVERVIEW.md](./OVERVIEW.md)** — the full narrative tour of how the gates, habit sensors, skills, and the self-improving `learn` loop fit together.

## The idea

A CI pipeline and a set of agent habits are usually built as two separate things. They shouldn't be. They are **one rule set in three placements**:

| Placement | When | Feedback to | Cost |
|---|---|---|---|
| In-loop | while the agent edits | the agent, mid-task | free — already in session |
| Pre-push | before code leaves the machine | you | free |
| CI | on pull request | the permanent record | free tier |

Run different rules in each and you get "passes locally, fails in CI", plus a failure specific to agents: the agent fixes what the hook reported, CI complains about something else, the agent fixes that and regresses the first.

## The verbs

```bash
mise run fix        # auto-fix what is mechanically fixable
mise run lint       # style + structural smells
mise run typecheck  # static types
mise run test       # tests + coverage floor
mise run audit      # vulnerabilities, secrets, SAST
mise run gate       # all of the above, in order. The oracle.
```

Callers invoke **verbs, never tools**. That is what lets one skill library serve a Kotlin repo and a React repo. Full rules in [CONTRACT.md](./CONTRACT.md).

## Using it in a repo

```yaml
# .github/workflows/gate.yml
jobs:
  gate:
    uses: CMaintz/foundry/.github/workflows/ts.yml@v1
```

Plus a `mise.toml` defining the six verbs. See [templates/](./mise/).

## Design

Two ideas do most of the work:

**Deterministic is the oracle; probabilistic only proposes.** Linters, types, tests and scanners decide pass/fail. A model produces a *patch*, which is accepted only if the deterministic gate then passes. A model's claim that it fixed something is not evidence — the exit code is.

**Ratchet, don't gate.** Retrofitting linters onto a real codebase means everything is red on day one, and you abandon it in week two. Record the existing violations as an accepted baseline that may only ever shrink. ESLint 9.24+ (`--suppress-all` / `--prune-suppressions`) and habit-hooks (`habit-snooze`) both have this built in — don't hand-roll it.

The corollary is enforced rather than requested: a PR that changes the ruleset *and* production source fails `ruleset-guard` unless a human labels it `ruleset-change`. Otherwise the cheapest fix for `high-complexity` is `// eslint-disable-next-line`.

Full rationale: [DESIGN.md](./DESIGN.md).

## Status

Early. TypeScript is the proven stack; Python, PHP and JVM are next. See DESIGN.md §10 for the rollout and §11 for what's still open.

## Licence

MIT.
