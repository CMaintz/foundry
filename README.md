# foundry

Reusable CI workflows, `mise` task templates and config presets behind a single six-verb interface, so the same rule set runs while an agent edits, before you push, and on the PR.

Companion repo: **[cmaintz-skills](https://github.com/CMaintz/cmaintz-skills)** — the agent half (skills, hooks). The seam between them is [CONTRACT.md](./CONTRACT.md), which is copied verbatim into both.

> **New here? Read [OVERVIEW.md](./OVERVIEW.md)** — the full narrative tour of how the gates, habit sensors, skills, and the self-improving `learn` loop fit together.
>
> **[FEATURES.md](./FEATURES.md)** is the canonical inventory of everything Foundry provides — and the backport checklist: anything non-language-specific built in a consumer repo comes back here.

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
| `ts.yml` · `java.yml` · `php.yml` | the language gate (six verbs, decomposed one-per-step with targeted fix summaries) + structural smells (which print a per-smell "fix toward" legend on failure). `java` adds opt-in `spotbugs` / `no_var` jobs |
| `tier0.yml` | language-agnostic: secret scan + `ruleset-guard` |
| `semgrep.yml` | SAST, diff-aware (only new findings fail) |
| `web.yml` | max-file-length gate for HTML/CSS |
| `bootstrap.yml` | regenerate the habit-hooks snooze baseline on Linux, open a PR |
| `ratchet-report.yml` | PR comment showing how the accepted-debt baselines moved |
| `autofix.yml` | add an `autofix` label to a PR → runs `mise run fix`, commits + pushes the result |

Split them across `gate.yml` / `quality.yml` / `security.yml` / `bootstrap.yml` (see [OVERVIEW.md](./OVERVIEW.md) §13).

### Presets

Shared config and agent-facing docs the scaffold copies (or, for the docs, `@`-include straight into your `AGENTS.md` / `CLAUDE.md`):

| Preset | What |
|---|---|
| [`habit-hooks/<stack>.toml`](./presets/habit-hooks/) | structural-smell config per stack — tests excluded, the language-independent `generic` duplication check everywhere ([details](./presets/habit-hooks/README.md)) |
| [`habit-hooks/java/guides/`](./presets/habit-hooks/java/guides/) | per-smell coaching for the Java sensor — concrete "fix toward this", rendered inline in-loop *and* in CI |
| [`pmd/ruleset.xml`](./presets/pmd/) · `pmd/no-var.xml` | tuned Java ruleset (`ExcessiveParameterList` ≥ 8) + the no-`var` rule |
| [`gitleaks.toml`](./presets/gitleaks.toml) · [`renovate.json`](./presets/renovate.json) | secret-scan allowlist starting point + the dependency-update path the "pin everything" rule needs |
| [`code-standards.md`](./presets/code-standards.md) · [`collaboration.md`](./presets/collaboration.md) · [`agent-loop.md`](./presets/agent-loop.md) | agent-facing standing docs — clean code (functions do one thing / SRP), working discipline (branch hygiene + sub-agents), and the self-correcting loop (observe → fix the cause → verify → repeat until green *and* honest) |
| [`ticket-schema.md`](./presets/ticket-schema.md) · [`ISSUE_TEMPLATE/agent-feature.yml`](./presets/ISSUE_TEMPLATE/agent-feature.yml) | the ticket the `/feature` driver works — intent, an acceptance-criteria checklist, scope, pointers — as a GitHub issue form or a local `tickets/*.md`. Copy the template into a consumer's `.github/ISSUE_TEMPLATE/` |

### From ticket to PR — the `/feature` driver

Foundry answers *"when is a change done?"* — a green gate. The **`/feature`** driver is the thing in front of that — **ticket in, PR out** — the [`feature`](https://github.com/CMaintz/cmaintz-skills) skill in cmaintz-skills, specified in [designs/backlog-feature-driver.md](./designs/backlog-feature-driver.md). Foundry ships the intake it consumes (the schema + issue template above); the driver:

1. **Claim** an `agent:ready` ticket — a GitHub Issue (via the [`agent-feature`](./presets/ISSUE_TEMPLATE/agent-feature.yml) form) or a local `tickets/*.md`, same [schema](./presets/ticket-schema.md) — flipping it to `agent:working` (atomic, WIP = 1) in its own worktree off `origin/main`.
2. **Loop to the gate** — implement → `mise run gate` → act on the failure + habit-hooks coaching → retry, *bounded* (≤ 5 cycles; bail early on no progress, posting the stuck state to the issue thread and flipping `agent:blocked`).
3. **Verify** the result against the ticket's acceptance-criteria checklist — green ≠ correct.
4. **Hand to `/ship`** — which re-gates, runs a fresh-context review against the linked issue, commits, and opens the PR. The driver never opens a PR itself, so there's one trusted path to `main`.

It re-implements none of the standards: the gate is the oracle, `ruleset-guard` + habit-hooks stop the loop gaming the metric, `/ship` is the handoff. Run it supervised — `/feature <ref>` — or as a backlog puller — `/loop <interval> /feature`.

### Versioning

Foundry follows semver on the reusable-workflow **interface** (workflow inputs and
the six-verb contract — not the internal steps):

- **patch** (`v1.0.1`) — a fix with no interface change.
- **minor** (`v1.1.0`) — a backward-compatible addition (a new workflow, a new
  optional input, a feedback improvement).
- **major** (`v2.0.0`) — a breaking change: an input renamed/removed, a verb's
  meaning changed, a workflow dropped. Only then must a consumer act.

Tag at **milestones** — a batch of merged PRs — not every commit; per-commit tags
are noise. Cut an immutable `vX.Y.Z` tag, then **move the `vX` alias** to it, so a
consumer pinning `@v1` rides non-breaking updates while `@v1.2.0` stays frozen.
Pin by SHA for maximum reproducibility (Renovate bumps it) or by `@v1` for
convenience. `CHANGELOG.md` records what each tag moved.

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
