# Changelog

What each Foundry release moved. Versioning policy: [README](./README.md#versioning)
— semver on the reusable-workflow *interface* (inputs + the six-verb contract), tag
at milestones, move the `vX` alias to the newest `vX.Y.Z`.

The format follows [Keep a Changelog](https://keepachangelog.com/).

## [1.3.0](https://github.com/CMaintz/foundry/compare/v1.2.0...v1.3.0) (2026-09-26)


### Features

* add feature-driver ticket schema, issue template, and design ([0d8e640](https://github.com/CMaintz/foundry/commit/0d8e640b5f62df3c9dc3597c3bd3c19bd686583b))
* **ci:** automated versioning via release-please + commitlint ([b2eb6d7](https://github.com/CMaintz/foundry/commit/b2eb6d7f99c2cd03a2a543614bcbf76aada717dc))
* **ci:** automated versioning via release-please + commitlint ([99bf775](https://github.com/CMaintz/foundry/commit/99bf775c4a014a9586596cfd32ff969ff4de9382))
* feature-driver ticket schema, issue template, and design ([b9a28d1](https://github.com/CMaintz/foundry/commit/b9a28d1a9472ca0f6d45471b5f9deaa3e3948b55))
* **habit-hooks:** jscpd test-exclusion preset + guard it ([b00e106](https://github.com/CMaintz/foundry/commit/b00e106a602625564afeb172cec4d10b638568a6))
* **habit-hooks:** jscpd test-exclusion preset + ruleset-guard it ([c7bdbe0](https://github.com/CMaintz/foundry/commit/c7bdbe026a69d032c6e489ade1443b7b5bea35e0))
* **labels:** reusable setup-labels.sh + wire into foundry-init; drop local-md ([3b2f9b0](https://github.com/CMaintz/foundry/commit/3b2f9b04afb851795327cfd3bbf24791a01ce5d0))
* setup-labels.sh + GitHub-only tickets (drop local-md) ([6e19907](https://github.com/CMaintz/foundry/commit/6e199078a08ed1579e4eb8cec3dce606205af187))
* **standards:** cohesion + magic values + size limits (file-length 300, line-length eslint, foundry-allow-smell) ([547d487](https://github.com/CMaintz/foundry/commit/547d487623f62fd8309b12e7384dc16fc5c71471))
* **standards:** foundry-allow-smell PMD marker + base eslint config (line-length) ([8faa2a6](https://github.com/CMaintz/foundry/commit/8faa2a6ebfeaf3c8f53c0e5f42ba90b6fbfc2b46))
* **tooling:** changed-scope, loop telemetry, arch fitness, flake triager, prompt-eval ([6df77cc](https://github.com/CMaintz/foundry/commit/6df77cc020debf3fbe80b0578fbea91dccdac3ab))
* **tooling:** changed-scope, telemetry, arch fitness, flake triager, prompt-eval ([14853b4](https://github.com/CMaintz/foundry/commit/14853b4d76891e9a6ad4895e8d6817ddaee4e177))


### Bug Fixes

* **docs:** 'criticals' -&gt; 'critical' in the gate demo ([d4bbe15](https://github.com/CMaintz/foundry/commit/d4bbe15e38fddc615940ae4e3f4be236f4da9533))
* **java preset:** disable jscpd (Node CLI) — keep generic's file-length only ([c9198b2](https://github.com/CMaintz/foundry/commit/c9198b2bc7aa0368c283237203999597a1627a30))

## [Unreleased]

### Added
- **Ticket → PR intake for the `/feature` driver**: `presets/ticket-schema.md` (the
  GitHub-Issue ticket the driver works — intent, acceptance-criteria checklist, scope,
  pointers; `agent:ready`/`working`/`blocked` state machine) and
  `presets/ISSUE_TEMPLATE/agent-feature.yml` (the issue form that enforces it). Design
  in `designs/backlog-feature-driver.md`; consumed by the `feature` skill in
  cmaintz-skills. README documents the ticket→PR flow.
- **`scripts/setup-labels.sh`** — idempotently creates the GitHub labels the workflows
  + ticket state machine need (agent:ready/working/blocked, align, ruleset-change,
  autofix); run by `foundry-init`.
- **jscpd pinned via mise** (`mise/java.toml` → `[tools] "npm:jscpd"`) — the `generic`
  plugin's duplicated-code detector now resolves the same version locally, in the
  habit-hooks-guard Stop hook, and in CI (`mise-action` runs `mise install`), instead of
  an unpinned `npm i -g jscpd` that could drift and shift duplication findings.
- **`presets/habit-hooks/jscpd.json`** — jscpd ignore list (tests + fixtures), fetched
  by `foundry-init` for the java stack. jscpd walks the dir itself and does NOT honor
  the `.habit-hooks` `files` exclusion, so without this, enabling duplication detection
  gates test code. The java preset's enable-jscpd instructions now point at it, and the
  snooze re-seed step.

### Changed
- Ticket transport is **GitHub Issues only** — dropped the half-specified local-md
  (`tickets/*.md`) fallback from the schema, design, and docs. `repo-align` now
  coordinates concurrent sessions through `align` issues (worktrees don't share
  local files).
- `tier0` ruleset-guard's default `ruleset_paths` now includes `.jscpd.json` — widening
  its ignore list loosens the duplication gate, so it needs the `ruleset-change` label
  alongside source (same governance as a snooze baseline or a PMD ruleset).
- **The smell gate scans only changed files** (`habit-hooks --branch`) in `java.yml`
  and `ts.yml`, instead of the whole tree every PR. Unchanged files are already covered
  by the snooze baseline; the full scan is a baseline-time job (`bootstrap`). Each habits
  job now creates a local `main` at the PR base so `--branch` resolves in a detached PR
  checkout (`ts.yml` gains `fetch-depth: 0`). habit-hooks errors loudly if the base ref
  is missing — it never silently passes an unscanned tree.

- **OVERVIEW §7 gains a gate-governance map** — one table of every gate-defining file
  (`snooze.json`, `eslint-suppressions.json`, `.jscpd.json`, rulesets/thresholds) →
  what protects it (hook / ruleset-guard / bootstrap) → the reminder to add new ones to
  `ruleset_paths`. `foundry-init` Next-steps now flags that some sensors ship disabled.

### Fixed
- `foundry-init` scaffolded the `bootstrap` cron as **weekly** (`0 6 * * 1`) after the
  intended cadence became daily — new repos now scaffold `0 6 * * *` (one shrink PR/day).

## [1.2.0] — 2026-09-17

### Added
- **`presets/agent-loop.md`** — the canonical self-correcting agent loop (observe →
  fix the cause → verify → repeat until green *and* honest), `@`-includable.
- **`presets/habit-hooks/java/guides/*.md`** — per-smell coaching for the Java
  sensor (oversized-function, high-complexity, too-many-parameters, deep-nesting),
  rendered inline in-loop and in CI.
- **PMD pinned + auto-provisioned** in `mise/java.toml` via a `setup:pmd` task + a
  `postinstall` hook (PMD can't be a `[tools]` entry), on `mise` PATH — local == CI.
- `foundry-init` sets `windows_default_inline_shell_args` in global mise config
  (mise refuses it in project config) and fetches the Java guides.
- README **Presets** section surfacing the agent docs + configs.

### Changed
- CI: cache PMD in the mise-install jobs (gate) so the postinstall provision doesn't
  re-download; `cache: true` on mise-action.

### Fixed
- `foundry-init` fetched `presets/habit-hooks/ts.toml` after it was renamed to
  `typescript.toml` — the `ts` stack 404'd on its smells config. Now maps `ts` →
  `typescript`.

## [1.1.0] — 2026-09-15

### Added
- **`presets/code-standards.md`** — agent-facing clean-code standard (functions do
  one thing / SRP), tied to the deterministic smells; `@`-includable.
- **`presets/collaboration.md`** — branch hygiene for parallel sessions + delegate
  to sub-agents; `@`-includable.
- **`FEATURES.md`** — canonical inventory + the backport discipline.
- **`autofix.yml`** — label a PR `autofix` → runs `mise run fix`, commits the result.
- Structural-smell jobs print a per-smell "fix toward" legend on failure.
- `bootstrap` caller is scheduled weekly so the snooze baseline auto-prunes.

### Changed
- Recommend running the gate suite **PR-only** (not `push:main`); the next PR's gate
  re-tests integrated main, so the push run is usually redundant. (OVERVIEW §13.)

### Fixed
- `[sensors.pmd] args` must be a TOML array (a string was mangled per-character).
- Every habit-hooks preset carries a positive `files` include (a bare `!exclusion`
  matched nothing and silently disabled the scan); `bootstrap` uses `--no-snooze`.
- `${{ github.* }}` passed through `env:` in `run:` steps (shell-injection).

## [1.0.0] — 2026-09-14

Initial release.

### Added
- **Reusable workflows:** `ts.yml` · `java.yml` · `php.yml` (six-verb language gate,
  decomposed one-per-step with targeted fix summaries, + structural smells), `tier0.yml`
  (secret scan + `ruleset-guard`), `semgrep.yml` (diff-aware SAST), `web.yml`,
  `bootstrap.yml`, `ratchet-report.yml`, `lint-workflows.yml`.
- **mise verb templates:** `ts` · `java` · `php` · `kotlin` · `dotnet` · `python`.
- **Presets:** habit-hooks configs per stack, tuned PMD ruleset + no-`var` rule,
  gitleaks allowlist, renovate.
- **Scripts:** `ruleset_guard.py` (per-entry, tightening-aware anti-gaming),
  `foundry-init.sh` (one-shot scaffold).
- **Docs:** OVERVIEW, CONTRACT, DESIGN.
- `ruleset-guard` is tightening-aware; merge-base–scoped so a stale base can't
  false-flag. node_modules caching for the TS gate.

### Fixed
- Reusable-workflow inputs are snake_case (`inputs.mise-version` parses as a
  subtraction and fails at startup).

[Unreleased]: https://github.com/CMaintz/foundry/compare/v1.2.0...HEAD
[1.2.0]: https://github.com/CMaintz/foundry/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/CMaintz/foundry/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/CMaintz/foundry/releases/tag/v1.0.0
