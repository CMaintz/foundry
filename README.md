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

Fastest path — the scaffold copies the templates + presets and generates the caller workflows, then prints the branch-protection checklist:

```bash
curl -fsSL https://raw.githubusercontent.com/CMaintz/foundry/main/scripts/foundry-init.sh -o foundry-init.sh
bash foundry-init.sh java        # stacks: ts | java | php | kotlin | dotnet | python
```

Or wire it by hand — a `mise.toml` with the six verbs (see [templates/](./mise/)) plus a caller workflow per concern:

```yaml
# .github/workflows/gate.yml
jobs:
  gate:
    uses: CMaintz/foundry/.github/workflows/java.yml@v1
```

### Reusable workflows

| Workflow | What it runs |
|---|---|
| `ts.yml` · `java.yml` · `php.yml` | the language gate (six verbs) + structural smells. `java` adds opt-in `spotbugs` / `no_var` jobs |
| `tier0.yml` | language-agnostic: secret scan + `ruleset-guard` |
| `semgrep.yml` | SAST, diff-aware (only new findings fail) |
| `web.yml` | max-file-length gate for HTML/CSS |
| `bootstrap.yml` | regenerate the habit-hooks snooze baseline on Linux, open a PR |
| `ratchet-report.yml` | PR comment showing how the accepted-debt baselines moved |
| `autofix.yml` | add an `autofix` label to a PR → runs `mise run fix`, commits + pushes the result |

Split them across `gate.yml` / `quality.yml` / `security.yml` / `bootstrap.yml` (see [OVERVIEW.md](./OVERVIEW.md) §13). [`presets/renovate.json`](./presets/renovate.json) keeps the pins fresh — the update path the "pin everything" rule needs.

## Design

Two ideas do most of the work:

**Deterministic is the oracle; probabilistic only proposes.** Linters, types, tests and scanners decide pass/fail. A model produces a *patch*, which is accepted only if the deterministic gate then passes. A model's claim that it fixed something is not evidence — the exit code is.

**Ratchet, don't gate.** Retrofitting linters onto a real codebase means everything is red on day one, and you abandon it in week two. Record the existing violations as an accepted baseline that may only ever shrink. ESLint 9.24+ (`--suppress-all` / `--prune-suppressions`) and habit-hooks (`habit-snooze`) both have this built in — don't hand-roll it.

The corollary is enforced rather than requested: a PR that changes the ruleset *and* production source fails `ruleset-guard` unless a human labels it `ruleset-change`. Otherwise the cheapest fix for `high-complexity` is `// eslint-disable-next-line`.

Full rationale: [DESIGN.md](./DESIGN.md).

## Status

TypeScript and Java are the proven stacks (Java via the AutoApplicant pilot — Spring Boot + Angular + a browser extension). PHP, Kotlin, .NET and Python have verb templates + presets; PHP has a reusable workflow. See DESIGN.md §10 for the rollout and §11 for what's still open.

## Licence

MIT.
