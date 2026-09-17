# Changelog

What each Foundry release moved. Versioning policy: [README](./README.md#versioning)
— semver on the reusable-workflow *interface* (inputs + the six-verb contract), tag
at milestones, move the `vX` alias to the newest `vX.Y.Z`.

The format follows [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Added
- **Ticket → PR intake for the `/feature` driver**: `presets/ticket-schema.md` (the
  ticket the driver works — intent, acceptance-criteria checklist, scope, pointers;
  GitHub-label state machine + local-md fallback) and
  `presets/ISSUE_TEMPLATE/agent-feature.yml` (the issue form that enforces it). Design
  in `designs/backlog-feature-driver.md`; the `/feature` skill itself lives in
  cmaintz-skills. README documents the ticket→PR flow.

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
