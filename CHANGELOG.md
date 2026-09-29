# Changelog

What each Foundry release moved. Versioning policy: [README](./README.md#versioning)
— semver on the reusable-workflow *interface* (inputs + the six-verb contract), tag
at milestones, move the `vX` alias to the newest `vX.Y.Z`.

The format follows [Keep a Changelog](https://keepachangelog.com/).

## [3.0.0](https://github.com/CMaintz/foundry/compare/v2.3.0...v3.0.0) (2026-09-29)


### ⚠ BREAKING CHANGES

* the CI API is now gate.yml + security.yml. Direct references to java.yml/ts.yml/php.yml/tier0.yml/semgrep.yml must move to the facades. @v1 keeps the old names frozen; adopt the facades at @v2.

### Features

* add feature-driver ticket schema, issue template, and design ([0d8e640](https://github.com/CMaintz/foundry/commit/0d8e640b5f62df3c9dc3597c3bd3c19bd686583b))
* add Java, PHP and HTML/CSS stacks ([1feb53b](https://github.com/CMaintz/foundry/commit/1feb53bbb1134bf342d298c8437065ade4c1efff))
* **bootstrap:** auto-merge prune baseline PRs ([8393e39](https://github.com/CMaintz/foundry/commit/8393e396327dbe61521f5870a178dd7392a2c262))
* **bootstrap:** auto-merge prune baseline PRs ([6cd0609](https://github.com/CMaintz/foundry/commit/6cd0609d8c343003f9cd7deec04c54cf9f7e3547))
* **bootstrap:** reusable habit-hooks baseline refresh + split/branch-protection docs ([9f2623d](https://github.com/CMaintz/foundry/commit/9f2623d597ef500fdc58cc92d7d7481c1937d4b7))
* **ci:** actionable failure summaries + cache semgrep install ([d26ea5a](https://github.com/CMaintz/foundry/commit/d26ea5a4688ef02823493bedbdd11f9aeb5e2b60))
* **ci:** add reusable java.yml and php.yml gate workflows ([a9d4ca2](https://github.com/CMaintz/foundry/commit/a9d4ca239dcf7cbb04695bac97fa7e15daa597bd))
* **ci:** autofix.yml — label-triggered `mise run fix` in CI ([c424b33](https://github.com/CMaintz/foundry/commit/c424b33ca4d930b05da0f0378af80bc0e1e1d906))
* **ci:** automated versioning via release-please + commitlint ([b2eb6d7](https://github.com/CMaintz/foundry/commit/b2eb6d7f99c2cd03a2a543614bcbf76aada717dc))
* **ci:** automated versioning via release-please + commitlint ([99bf775](https://github.com/CMaintz/foundry/commit/99bf775c4a014a9586596cfd32ff969ff4de9382))
* **ci:** decompose the gate into per-verb steps with targeted fixes ([9c7250d](https://github.com/CMaintz/foundry/commit/9c7250d772f1932241da0a1d639ff695f6636391))
* **ci:** ratchet-report PR comment making baseline movement visible ([cf67a2f](https://github.com/CMaintz/foundry/commit/cf67a2f3b641bb9a93f2133ff21537c7cd29dc5a))
* **dotnet:** first-class .NET/C# stack ([9a9f41d](https://github.com/CMaintz/foundry/commit/9a9f41d2f7a481bc86bb4a2bbdd49c4e4c8e0e36))
* **dotnet:** first-class .NET/C# stack via the gate facade ([05393fe](https://github.com/CMaintz/foundry/commit/05393fe7603c74f6703341279eea31aa5be8d949))
* facade API — gate.yml/security.yml front the per-stack internals ([bc3577f](https://github.com/CMaintz/foundry/commit/bc3577fd6a5cf13b5b92f00f3b125bedae145cca))
* feature-driver ticket schema, issue template, and design ([b9a28d1](https://github.com/CMaintz/foundry/commit/b9a28d1a9472ca0f6d45471b5f9deaa3e3948b55))
* **habit-hooks:** jscpd test-exclusion preset + guard it ([b00e106](https://github.com/CMaintz/foundry/commit/b00e106a602625564afeb172cec4d10b638568a6))
* **habit-hooks:** jscpd test-exclusion preset + ruleset-guard it ([c7bdbe0](https://github.com/CMaintz/foundry/commit/c7bdbe026a69d032c6e489ade1443b7b5bea35e0))
* **habit-hooks:** port pilot lessons into presets ([d163e47](https://github.com/CMaintz/foundry/commit/d163e4730b3145e5770924e1448ce8cff6169e8b))
* initial Foundry gate — verb interface, reusable workflows, design ([7b7460b](https://github.com/CMaintz/foundry/commit/7b7460badaaf6ecb74dda1176be928687f01e3ea))
* **labels:** reusable setup-labels.sh + wire into foundry-init; drop local-md ([3b2f9b0](https://github.com/CMaintz/foundry/commit/3b2f9b04afb851795327cfd3bbf24791a01ce5d0))
* **mise/java:** pin + auto-provision PMD ([6dccf14](https://github.com/CMaintz/foundry/commit/6dccf14da801e244f115ba203a29905c22a15e61))
* **mise/java:** pin + auto-provision PMD (setup:pmd task + postinstall hook) ([aceec97](https://github.com/CMaintz/foundry/commit/aceec97ac6d3834bdd02b3b46c7583ccb58a3579))
* per-smell Java guides preset + foundry-init sets shell-args globally ([0b6227f](https://github.com/CMaintz/foundry/commit/0b6227f2bb5f8bac32124528990e3a7560163d35))
* **preset:** agent-loop.md — the canonical self-correcting agent loop ([d321861](https://github.com/CMaintz/foundry/commit/d3218611becd9143fd2b0787299daa204a2edb48))
* **preset:** agent-loop.md — the canonical self-correcting loop ([29d0f7b](https://github.com/CMaintz/foundry/commit/29d0f7bff08a602f2c83f2bc6b653e528c458676))
* **renovate:** dependency-update automation to close the pin-everything loop ([2a04ab4](https://github.com/CMaintz/foundry/commit/2a04ab42f6050f57b9a899dd2d1e30ddcb9761de))
* **scaffold:** foundry-init — one-shot onboarding for a repo ([c01d778](https://github.com/CMaintz/foundry/commit/c01d77889e8685a6983be79fcaf8b51d21f43881))
* **scaffold:** schedule the generated bootstrap caller (weekly auto-prune) ([a062b59](https://github.com/CMaintz/foundry/commit/a062b59c992b99de6f0a480f45a7820e00d7b0a9))
* setup-labels.sh + GitHub-only tickets (drop local-md) ([6e19907](https://github.com/CMaintz/foundry/commit/6e199078a08ed1579e4eb8cec3dce606205af187))
* ship per-smell Java guides + set shell-args globally in foundry-init ([c3edfe0](https://github.com/CMaintz/foundry/commit/c3edfe04290518f0ad0d24cf7073781934036d9b))
* **stacks:** add kotlin, dotnet and python verb templates + presets ([f80d97d](https://github.com/CMaintz/foundry/commit/f80d97df4cfa1f93c8495931cf386255c16dd8c2))
* **standards:** add code-standards.md — functions do one thing (SRP) ([4e5c0f2](https://github.com/CMaintz/foundry/commit/4e5c0f268118c6e47087e1f88ad49a3266c71a4d))
* **standards:** cohesion + magic values + size limits (file-length 300, line-length eslint, foundry-allow-smell) ([547d487](https://github.com/CMaintz/foundry/commit/547d487623f62fd8309b12e7384dc16fc5c71471))
* **standards:** foundry-allow-smell PMD marker + base eslint config (line-length) ([8faa2a6](https://github.com/CMaintz/foundry/commit/8faa2a6ebfeaf3c8f53c0e5f42ba90b6fbfc2b46))
* **tier0:** make ruleset-guard tightening-aware ([fbf4c02](https://github.com/CMaintz/foundry/commit/fbf4c020582f78ea25ef495fa81ce71973676110))
* **tooling:** changed-scope, loop telemetry, arch fitness, flake triager, prompt-eval ([6df77cc](https://github.com/CMaintz/foundry/commit/6df77cc020debf3fbe80b0578fbea91dccdac3ab))
* **tooling:** changed-scope, telemetry, arch fitness, flake triager, prompt-eval ([14853b4](https://github.com/CMaintz/foundry/commit/14853b4d76891e9a6ad4895e8d6817ddaee4e177))
* **ts:** ratcheted npm audit for the audit verb ([760c0e0](https://github.com/CMaintz/foundry/commit/760c0e027d7586016dadf2b9afacc8ee4eb9e229))
* **ts:** ratcheted npm audit for the audit verb ([b5086d6](https://github.com/CMaintz/foundry/commit/b5086d6b70930de266fec5f3d14b9a3e562fe91f))
* **ts:** typecheck requires a tsconfig and type-checks Deno code ([e28f777](https://github.com/CMaintz/foundry/commit/e28f7770d89afbf68e4079a648db5b89865780da))
* **ts:** typecheck requires a tsconfig and type-checks Deno code ([c1a840c](https://github.com/CMaintz/foundry/commit/c1a840cf5186c6dba4c4f753aef483179b0922e7))


### Bug Fixes

* **ci:** pass github context via env in run: steps (shell-injection) ([d677a73](https://github.com/CMaintz/foundry/commit/d677a73950fc90ed08a7d95bde297a7746cafa38))
* **ci:** security facade startup failure and ratchet-report on a new baseline ([ce67565](https://github.com/CMaintz/foundry/commit/ce67565314422fa22293141e3beabbc790826e31))
* **ci:** security facade startup failure and ratchet-report on a new baseline ([5e16845](https://github.com/CMaintz/foundry/commit/5e16845f82440eddb408b7a20d3176db9f15fc55))
* **docs:** 'criticals' -&gt; 'critical' in CHANGELOG (typos check) ([cc07276](https://github.com/CMaintz/foundry/commit/cc0727618f0f712f6b7dd97fdee8acc154437dd6))
* **docs:** 'criticals' -&gt; 'critical' in the gate demo ([d4bbe15](https://github.com/CMaintz/foundry/commit/d4bbe15e38fddc615940ae4e3f4be236f4da9533))
* **habit-hooks:** [sensors.pmd] args must be a TOML array (string is mangled) ([d3b6f1c](https://github.com/CMaintz/foundry/commit/d3b6f1ce5e27fdd9f4fa8af546e0c03c3df6cca2))
* **habit-hooks:** name the tuned PMD ruleset via -R, not silent discovery ([e6db03d](https://github.com/CMaintz/foundry/commit/e6db03d23ede9d47d50016b113187dd447b12338))
* **habit-hooks:** positive include in every preset (bare exclusion scanned nothing) + bootstrap --no-snooze ([8871126](https://github.com/CMaintz/foundry/commit/88711265f073b63ab11d1e7713095b24d1a906d4))
* **java preset:** disable jscpd (Node CLI) — keep generic's file-length only ([c9198b2](https://github.com/CMaintz/foundry/commit/c9198b2bc7aa0368c283237203999597a1627a30))
* **tier0:** guard diffs from merge-base so a stale base.sha can't false-flag ([55d2c1c](https://github.com/CMaintz/foundry/commit/55d2c1cbecf56dbff379368c66a576e479b3ee6d))
* **tier0:** per-entry loosening check via scripts/ruleset_guard.py ([49dbf13](https://github.com/CMaintz/foundry/commit/49dbf1364a647423682ee4a9cca677b2fc06e3b7))
* **workflows:** snake_case reusable-workflow inputs ([1ba6c33](https://github.com/CMaintz/foundry/commit/1ba6c33c117bcf3dafbc1c54fac4d09595fe39a5))


### Performance Improvements

* **ts:** cache node_modules to skip npm ci rebuilds ([1a13564](https://github.com/CMaintz/foundry/commit/1a1356437467184d725e820fe854f9b3ab13b019))

## [2.3.0](https://github.com/CMaintz/foundry/compare/v2.2.0...v2.3.0) (2026-09-29)


### Features

* **ts:** ratcheted npm audit for the audit verb ([760c0e0](https://github.com/CMaintz/foundry/commit/760c0e027d7586016dadf2b9afacc8ee4eb9e229))
* **ts:** ratcheted npm audit for the audit verb ([b5086d6](https://github.com/CMaintz/foundry/commit/b5086d6b70930de266fec5f3d14b9a3e562fe91f))
* **ts:** typecheck requires a tsconfig and type-checks Deno code ([e28f777](https://github.com/CMaintz/foundry/commit/e28f7770d89afbf68e4079a648db5b89865780da))
* **ts:** typecheck requires a tsconfig and type-checks Deno code ([c1a840c](https://github.com/CMaintz/foundry/commit/c1a840cf5186c6dba4c4f753aef483179b0922e7))


### Bug Fixes

* **ci:** security facade startup failure and ratchet-report on a new baseline ([ce67565](https://github.com/CMaintz/foundry/commit/ce67565314422fa22293141e3beabbc790826e31))
* **ci:** security facade startup failure and ratchet-report on a new baseline ([5e16845](https://github.com/CMaintz/foundry/commit/5e16845f82440eddb408b7a20d3176db9f15fc55))

## [2.2.0](https://github.com/CMaintz/foundry/compare/v2.1.0...v2.2.0) (2026-09-28)


### Features

* **dotnet:** first-class .NET/C# stack ([9a9f41d](https://github.com/CMaintz/foundry/commit/9a9f41d2f7a481bc86bb4a2bbdd49c4e4c8e0e36))

## [2.1.0](https://github.com/CMaintz/foundry/compare/v2.0.0...v2.1.0) (2026-09-27)


### Features

* **bootstrap:** auto-merge prune baseline PRs ([8393e39](https://github.com/CMaintz/foundry/commit/8393e396327dbe61521f5870a178dd7392a2c262))

## [2.0.0](https://github.com/CMaintz/foundry/compare/v1.2.0...v2.0.0) (2026-09-27)


### ⚠ BREAKING CHANGES

* the CI API is now gate.yml + security.yml. Direct references to java.yml/ts.yml/php.yml/tier0.yml/semgrep.yml must move to the facades. @v1 keeps the old names frozen; adopt the facades at @v2.

### Features

* add feature-driver ticket schema, issue template, and design ([0d8e640](https://github.com/CMaintz/foundry/commit/0d8e640b5f62df3c9dc3597c3bd3c19bd686583b))
* **ci:** automated versioning via release-please + commitlint ([b2eb6d7](https://github.com/CMaintz/foundry/commit/b2eb6d7f99c2cd03a2a543614bcbf76aada717dc))
* **ci:** automated versioning via release-please + commitlint ([99bf775](https://github.com/CMaintz/foundry/commit/99bf775c4a014a9586596cfd32ff969ff4de9382))
* facade API — gate.yml/security.yml front the per-stack internals ([bc3577f](https://github.com/CMaintz/foundry/commit/bc3577fd6a5cf13b5b92f00f3b125bedae145cca))
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

* **docs:** 'critical' -&gt; 'critical' in the gate demo ([d4bbe15](https://github.com/CMaintz/foundry/commit/d4bbe15e38fddc615940ae4e3f4be236f4da9533))
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
