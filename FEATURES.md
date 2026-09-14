# FEATURES — the canonical inventory

**Purpose.** One place listing everything Foundry provides, so that when a feature
is built or improved *inside a consumer repo* (e.g. AutoApplicant), it's obvious
what should come back here. If a capability isn't in this list, it either doesn't
exist yet or it hasn't been backported — both are actionable.

## Backport discipline

**Every change that is not language-specific gets backported to foundry (or the
shared preset) the same day it's proven in a consumer repo.** Language-specific
details (a Spring version override, an app's Docker publish) stay in the consumer.
Everything else — a workflow pattern, a guard fix, a feedback improvement, a hook,
a preset tweak — is Foundry's and belongs here. When in doubt, backport: the cost
of a duplicated line in foundry is far less than the cost of drift.

Rule of thumb for "is it language-specific?": would a Kotlin repo and a React repo
both want it? If yes → foundry. If it names a single language's tool *as the
mechanism* (not just an example) → a per-language file (`mise/<lang>.toml`,
`presets/habit-hooks/<lang>.toml`), still in foundry.

## Reusable workflows (`.github/workflows/`)

| Workflow | Purpose |
|---|---|
| `ts.yml` · `java.yml` · `php.yml` | Language gate — the six verbs, decomposed one-per-step with targeted failure summaries, + a structural-smells job. `java` adds opt-in `spotbugs` / `no_var`. node_modules / vendor / Gradle caching. |
| `tier0.yml` | Language-agnostic: secret scan (gitleaks) + `ruleset-guard`, both with remediation step-summaries. Merge-base–scoped. |
| `semgrep.yml` | SAST, diff-aware (`--baseline-commit`), pip-cached, pinnable. |
| `web.yml` | Max-file-length gate for HTML/CSS. |
| `bootstrap.yml` | Regenerate the habit-hooks snooze baseline on Linux (`--prune` to shrink), open a PR. |
| `ratchet-report.yml` | PR comment showing how the accepted-debt baselines moved. |
| `autofix.yml` | Label a PR `autofix` → runs `mise run fix`, commits + pushes the result. |
| `lint-workflows.yml` | actionlint over foundry's own workflows. |

## mise verb templates (`mise/`)

`ts` · `java` · `php` · `kotlin` · `dotnet` · `python` — each exposes the six verbs
(`fix`/`lint`/`typecheck`/`test`/`audit`/`gate`), gate sequential.

## Presets (`presets/`)

| Preset | Purpose |
|---|---|
| `habit-hooks/{ts,java,php,kotlin,dotnet,python}.toml` | Structural-smell config per stack; tests excluded; Java names its tuned ruleset via `-R`. |
| `pmd/ruleset.xml` | Tuned Java ruleset (`ExcessiveParameterList` minimum 8). |
| `pmd/no-var.xml` | The no-`var` rule (diff-scoped in CI). |
| `gitleaks.toml` | Secret-scan allowlist starting point. |
| `renovate.json` | Dependency-update automation — the update path the pin-everything rule needs. |
| `code-standards.md` | Agent-facing clean-code standard (functions do one thing / SRP), tied to the deterministic smells. `@`-include into AGENTS.md/CLAUDE.md. |

## Scripts (`scripts/`)

- `ruleset_guard.py` — per-entry, tightening-aware anti-gaming check.
- `foundry-init.sh` — one-shot repo scaffold.

## Agent half — `cmaintz-skills`

- **Skills:** `ship`, `review`, `repo-align`, `foundry-secret`.
- **Hooks:** `habit-hooks-guard` (Stop, smells), `auto-format` (PostToolUse, per-edit
  prettier/eslint), `format-java-stop` (Stop, ratcheted Spotless),
  `typecheck-stop` (Stop, type errors), `guard-generated-files` (PreToolUse, blocks hand-editing snooze/suppressions), `pre-push` (git hook). All portable sh.

## Cross-cutting mechanisms

- **Deterministic oracle / probabilistic proposer** — the gate decides; the model proposes.
- **Ratcheting** — baselines that may only shrink (ESLint suppressions, snooze, coverage floors, Spotless/Semgrep/PMD diff-scoping).
- **`ruleset-guard`** — a source+ruleset PR that loosens the gate needs a `ruleset-change` label; merge-base–scoped so a stale base can't false-flag.
- **Placement triad** — in-loop (hooks) / pre-push (`/ship`, git pre-push) / CI, one rule set, no drift.
- **CI split + branch protection** — gate/quality/security/deploy/bootstrap; the gotchas and the path-filter+aggregate pattern live in [OVERVIEW.md](./OVERVIEW.md) §13.
