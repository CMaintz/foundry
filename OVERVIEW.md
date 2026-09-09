# Foundry — how the whole thing works

A narrative tour of the system: the harness engineering, the gates, the habit
sensors, the skills, and the loop that lets an agent get better at a codebase
over time. If you read one document, read this one.

For the rules themselves see [CONTRACT.md](./CONTRACT.md); for the design
rationale and decisions see [DESIGN.md](./DESIGN.md).

---

## 1. The one idea

A CI pipeline and a set of "AI coding standards" are usually built as two
separate things that slowly disagree with each other. Foundry's whole premise is
that they are **one rule set, run in three places**:

| Placement | When it runs | Who it talks to | What runs |
|---|---|---|---|
| **In-loop** | while the agent is editing | the agent, mid-task | `habit-hooks` (a Stop hook) |
| **Pre-push** | before code leaves your machine | you | `mise run gate` (via `/ship`) |
| **CI** | on every pull request | the permanent record | the same gate + guards |

Run *different* rules in each and you get "passes locally, fails in CI", plus a
failure mode unique to agents: the agent fixes what the hook flagged, CI
complains about something else, the agent fixes that and regresses the first
thing. One rule set, three placements, no drift.

## 2. The two repos and the one tool

The system is three moving parts, deliberately separated by who consumes them:

- **`foundry`** (this repo) — the CI half. Reusable GitHub Actions workflows,
  `mise` task templates, config presets. Consumed by *repositories*.
- **`cmaintz-skills`** — the agent half. Claude Code skills and hooks
  (`ship`, the habit-hooks Stop hook). Consumed by *Claude Code* as an installed
  plugin.
- **`habit-hooks`** — a third-party tool (installed via `uv`), not written by
  us. It's the structural-smell sensor layer, and Foundry borrows its
  tool-independent smell vocabulary as a backbone.

The seam between `foundry` and `cmaintz-skills` is [CONTRACT.md](./CONTRACT.md),
copied verbatim into both. If those two copies ever need to differ, the split
was wrong.

## 3. The verb interface — the thing that makes it polyglot

Every repo, whatever language, exposes the **same six verbs** through `mise`:

```
mise run fix        # auto-fix what is mechanically fixable
mise run lint       # style + structural smells (non-mutating)
mise run typecheck  # static types
mise run test       # tests + coverage floor
mise run audit      # vulnerabilities, secrets, SAST
mise run gate       # all of the above, in order. THE ORACLE.
```

Everything else in the system — CI, the git hooks, the `ship` skill — calls
**verbs, never tools**. A skill says `mise run lint`; it never says `eslint` or
`phpstan`. That indirection is the entire reason one skill library can serve a
React repo and a Kotlin repo: the smell vocabulary is language-independent, only
the tool behind each verb changes.

`mise` also pins the toolchain (`node = "22.14.0"`), which kills
"works-on-my-machine" between a laptop and the CI runner at the same time.

## 4. Deterministic vs probabilistic — who is allowed to decide

This is the load-bearing distinction in the whole design.

- **Deterministic layer = the oracle.** Formatters, linters, type checkers,
  tests + coverage, dependency/secret/SAST scanners. Pinned, reproducible,
  offline-capable. **These decide pass/fail. Nothing else does.**
- **Probabilistic layer = a proposer, never an authority.** An LLM's output is a
  *patch*. A patch is accepted only if the deterministic gate then passes from a
  clean tree. A model's *claim* that it fixed something is not evidence — the
  exit code is.

Concretely: an agent may run `mise run fix`, may act on habit-hooks' coaching,
may write code — but "done" is defined solely as a green `mise run gate`. The
agent proposes; the gate disposes.

Three probabilistic *roles* are kept deliberately separate (people mush them):

1. **Fixer** — given a failure + coaching, produce a patch. Bounded.
2. **Reviewer** — the things a linter genuinely can't judge: naming, domain
   drift, "is this the right seam", spec compliance. **Advisory, never blocking.**
3. **Triager** — flaky vs real, dedupe, route to a ticket.

## 5. The gate, job by job

The CI gate (`gate.yml`, or foundry's reusable `ts.yml` + `tier0.yml`) is four
jobs. CI is **100% deterministic on purpose** — no model, no API key, no secrets
beyond the default token.

- **`gate` (Deterministic gate)** — runs `mise run gate`: the exact verb a
  developer runs locally. If this and a laptop ever disagree, that's a bug in the
  setup, not the code.
- **`habits` (Structural smells)** — runs `habit-hooks`. Fails on *new* smells
  beyond the snoozed baseline (see §6).
- **`secrets` (Secret scan)** — gitleaks over full history.
- **`ruleset-guard`** — the anti-gaming control (see §7).

## 6. habit-hooks — coaching, not just failing

`habit-hooks` is the reflex layer. It wraps detectors (eslint, knip, ts-morph,
jscpd, PMD, phpmd, ruff…) and maps their findings onto **tool-independent
smells**: `oversized-file`, `oversized-function`, `too-many-parameters`,
`high-complexity`, `deep-nesting`, duplication, dead code. A smell means the same
thing in Kotlin and PHP; only the detector differs.

What makes it more than a linter: when it fails, it emits **coaching** aimed at
the agent, and that coaching argues *against* mechanical compliance —
"splitting a file at line 200 into `foo-1.ts` and `foo-2.ts` satisfies the
threshold while leaving the real problem in place." That anti-gaming framing is
why it's used to *teach* an agent rather than just gate it.

It runs in two placements:

- **In-loop:** a global **Stop hook** (`~/.claude/settings.json`) fires
  `habit-hooks-guard.ps1` when the agent is about to finish — but only in repos
  that opted in by having a `.habit-hooks/` directory, so it's silent everywhere
  else and safe to install globally. It's a *Stop* hook, not *PostToolUse*,
  because habit-hooks costs ~25s cold (~6s warm) — far too slow to fire after
  every edit, and it matches habit-hooks' own guidance: "run before considering
  work complete."
- **CI:** the `habits` job.

Config lives in **two** places, and it matters which:

- **Global** (`~/.claude/settings.json`): the Stop-hook wiring only.
- **Per-repo** (`.habit-hooks/config.toml`, `.habit-hooks/snooze.json`): which
  plugins are on, and the accepted-baseline of existing smells. Committed with
  the code.

## 7. Ratchets, not walls — and the guard that protects them

Retrofitting linters onto a real codebase makes *everything* red on day one, and
you abandon it in week two. So Foundry never gates on absolute cleanliness; it
**ratchets**:

- ESLint's native bulk suppression (`--suppress-all` / `--prune-suppressions`)
  records existing violations in `eslint-suppressions.json`.
- habit-hooks' `habit-snooze` records existing smells in `snooze.json`.
- Coverage floors are set to *today's real number*, not an aspiration.

Each baseline is committed and may **only ever shrink**. Fix an `any`, and
`--prune-suppressions` removes it from the baseline permanently.

The obvious attack on any ratchet is to weaken the rule instead of fixing the
code — the cheapest fix for `high-complexity` is `// eslint-disable`. So
**`ruleset-guard`** enforces mechanically: a PR that changes a ruleset file
(configs, thresholds, suppression baselines) *and* production source is blocked
unless a human applies the `ruleset-change` label.

The guard is **tightening-aware** — the risk is one-directional. *Loosening*
needs a human; *tightening*, or a change with no semantic effect, never does. So
a bundled ruleset+source PR passes without a label when every ruleset file it
touches is proven not to loosen the gate: a suppression baseline whose count only
shrank, a snooze list that only got shorter, or a pure CRLF/LF flip. This is what
lets `mise run fix` prune the baseline and ship that in the same PR as the fix.

## 8. The skills ecosystem — and how it touches the gate

Foundry's own skill layer is deliberately thin, because most of the *practice*
layer is already written well by others. They're installed as plugins (not
vendored), so upstream fixes flow and attribution stays put.

| Source | Role | How it touches the gate |
|---|---|---|
| **habit-hooks** | reflex / enforcement | *is* the `habits` placement; coaching feeds the fixer |
| **mattpocock/skills** | breadth of practice: `tdd`, `diagnosing-bugs`, `research`, `codebase-design`, `code-review` (Standards+Spec)… | procedures the agent runs; `ship` calls `code-review` |
| **devill/ivetts-skills** | the flywheel: `learn`, `hotspot-rec`, `build-project-review` | `learn` routes lessons *into* the gate; `hotspot-rec` reads git history for what to improve |
| **cmaintz-skills** (ours) | `ship` (pre-PR orchestration) + the habit-hooks hook | drives the whole gate locally |

Three layers, cleanly divided:

- **Reflex** → hooks (habit-hooks, pre-commit). Involuntary.
- **Practice** → skills (`tdd`, `ship`, `code-review`…). Invoked, procedural.
- **Standing context** → `AGENTS.md` + `CONTEXT.md`. Ambient shared vocabulary.
  (`CLAUDE.md` is a one-line include of `AGENTS.md`, so Codex/Gemini/Cursor read
  the same source.)

### `ship` — the local orchestrator

`/ship` is where a change goes from working tree to PR, running the gate before
the PR exists (which is what keeps CI free of API keys):

1. `mise run fix` — mechanical fixes land silently
2. `habit-hooks` — coaching → the agent fixes the smells
3. **`mise run gate` — must be green.** The oracle, not the agent's opinion.
4. **Review in a fresh context** — a sub-agent that sees only the diff and the
   spec, never the conversation that wrote the code (an agent reviewing its own
   work reviews its *intent*, not its *diff*). Uses a repo-local
   `build-project-review` skill if present, else `mattpocock-skills:code-review`.
5. Conventional commit → `gh pr create`.

### The three reviewers are a stack, not a clash

Installing everything leaves three things called "code review". They layer,
most-specific first: a repo-local `build-project-review` skill → Matt's
`code-review` (Standards + Spec) → the built-in `/code-review` (fast manual bug
hunt). They namespace as `plugin:skill`, so nothing actually collides.

## 9. The self-improving loop — `learn`

This is what makes the system get *better* rather than just stay clean. Ivett's
`learn` skill reflects on a session and routes each lesson to the store that will
actually **enforce** it, in priority order:

1. **a deterministic hook / check** — enforcement, so the mistake becomes
   impossible
2. **`AGENTS.md` / `CLAUDE.md`** — standing context
3. **a new skill** — a reusable procedure
4. **auto-memory** — last resort

That ordering *is* the project's thesis expressed as a skill: prefer the
placement that makes a mistake impossible over the one that merely reminds you
not to make it. A one-off fix in this session becomes a rule the next session
can't skip. Unlike habit-hooks, `learn` is a *model-invoked* skill (not a hook) —
it can't auto-fire, so the practice is to run `/learn` at session boundaries,
before anything gets written to memory.

The loop, end to end:

```
work → habit-hooks flags a smell → agent fixes it → /learn decides:
  "this class of mistake should be impossible" → new deterministic check
  → next time, the gate catches it before a human ever sees it
```

## 10. Language coverage — where it actually is

Proven and built out: **TypeScript / Node** (`mise/ts.toml`, `ts.yml`, eslint +
tsc + vitest + habit-hooks-typescript).

Reachable cheaply (habit-hooks already has detectors): **Java** (PMD), **PHP**
(phpmd), **Python** (ruff), **Ruby** (rubocop). Each needs a `mise` template +
a workflow.

No habit-hooks support, would use native tooling: **C#/.NET** (Roslyn analyzers /
editorconfig), **Kotlin** (detekt), **Swift** (SwiftLint), **HTML/CSS** (a
line-count / max-file gate, since the full smell suite doesn't apply).

The architecture is additive: a new stack is a new `mise` template and a new
reusable workflow, mapping that language's tools onto the same six verbs and the
same smell names. Nothing already built changes.

## 11. Where everything lives (quick map)

```
~/.claude/settings.json         # global: the habit-hooks Stop hook, no-attribution config
~/.claude/hooks/                # the hook script (habit-hooks-guard.ps1)

<repo>/mise.toml                # the six verbs for this repo
<repo>/.habit-hooks/            # config.toml + snooze.json (the smell baseline)
<repo>/eslint-suppressions.json # the lint baseline (ratchet)
<repo>/.github/workflows/       # the gate (inline, or calling foundry)
<repo>/AGENTS.md                # standing context (CLAUDE.md @-includes it)

foundry/                        # reusable workflows, mise templates, this doc
cmaintz-skills/                 # ship skill + the hook, as an installable plugin
```
