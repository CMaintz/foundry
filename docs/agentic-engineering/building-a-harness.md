# Building a harness

[Start](README.md) > [Working with agents](workflow.md) > **Building a harness** > [Evaluating the harness](evaluating.md)

## What the industry recommends

The field has converged on the same conclusion during 2026: model quality is no longer the bottleneck; the environment around the model is. "Harness engineering" became the name for that work in February 2026.

### The evidence that a harness matters

- **AI amplifies what is already there.** Google's [DORA 2025 report](https://dora.dev/dora-report-2025/) (about 5,000 respondents) found roughly 90% of tech professionals use AI, and that AI now correlates with higher delivery throughput, but delivery instability keeps rising too. Its core finding: AI magnifies an organisation's existing strengths and weaknesses ([InfoQ summary](https://www.infoq.com/news/2025/09/dora-state-of-ai-in-dev-2025)).
- **Feeling faster is not being faster.** In [METR's 2025 controlled trial](https://metr.org/blog/2025-07-10-early-2025-ai-experienced-os-dev-study/), 16 experienced developers on their own large codebases were 19% slower with AI, while believing they were 20% faster. The tools have improved since, but the lesson stands: measure, don't trust the feeling.
- **Trust is low.** Only 3% of developers report high trust in AI output (Stack Overflow 2025, cited by InfoQ). Deterministic gates are how a team earns trust it can't get from the model alone.

### The main frameworks

- **OpenAI: harness engineering.** A small team shipped a beta of about a million lines of code in five months with no hand-written source. Engineers designed environments and gave structured feedback; docs became the system of record; architecture layers were enforced by linters and structural tests; recurring "garbage collection" agents cleaned up drift ([InfoQ](https://www.infoq.com/news/2026/02/openai-harness-engineering-codex)).
- **Thoughtworks / Martin Fowler: guides and sensors.** Birgitta Böckeler's [Harness Engineering](https://martinfowler.com/articles/harness-engineering.html) (April 2026) splits a harness into **guides** that steer before the agent acts and **sensors** that observe after and help it self-correct. Each is either computational (tests, linters, types: fast, cheap, deterministic) or inferential (instructions, AI review: semantic, slower, non-deterministic). Feedback alone gives an agent that repeats mistakes; guidance alone gives one that never learns whether the rules worked. She also proposes shared **harness templates** across an organisation ([first memo](https://www.martinfowler.com/articles/exploring-gen-ai/harness-engineering-memo.html)).
- **Anthropic: Claude Code best practices.** The [official guide](https://code.claude.com/docs/en/best-practices) centres on one constraint: the context window fills fast and performance degrades as it fills. Its top recommendation is to give the agent a check it can run, "the difference between a session you watch and one you walk away from."

### How the recommendations map onto my setup

| Recommendation                                                                 | Source         | How I implement it                                                                                                                                              |
| ------------------------------------------------------------------------------ | -------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Give the agent a runnable pass/fail check                                      | Anthropic      | `mise run gate` is the definition of done; `ship` and the pre-push hook refuse to proceed until it passes, and Stop hooks block on smells and type errors first |
| Hooks for anything that must happen every time; instruction files are advisory | Anthropic      | reflex layer: formatter, smell sensor, type check, baseline and PR guards                                                                                       |
| Keep `CLAUDE.md` short; prune any line whose removal wouldn't cause a mistake  | Anthropic      | `AGENTS.md` canonical and lean; `learn` promotes repeated rules into hooks                                                                                      |
| Explore, plan, then code; interview the user for a spec                        | Anthropic      | `spec` skill produces a ticket with acceptance criteria before `feature` codes                                                                                  |
| A fresh-context reviewer that sees only the diff and criteria                  | Anthropic      | `ship` and `review` run reviewers as fresh sub-agents against the linked issue                                                                                  |
| Combine computational and inferential guides and sensors                       | Fowler         | gate and guards decide; skills, coaching and AI review advise                                                                                                   |
| Sensor output written for the agent, with fix instructions                     | Fowler         | habit-hooks coaching explains the deep fix and argues against gaming                                                                                            |
| Keep quality left: fast checks early, expensive ones in the pipeline           | Fowler         | per-edit, per-turn, pre-push and CI placements ranked by cost                                                                                                   |
| Architecture enforced mechanically                                             | OpenAI, Fowler | ArchUnit, dependency-cruiser and import-linter presets with frozen baselines                                                                                    |
| Shared harness templates across teams                                          | Fowler         | Foundry facades pinned at `@v2`, plus a scaffold that wires a new repo in one command                                                                           |
| Parallel sessions in isolated worktrees                                        | Anthropic      | one worktree, branch and PR per agent, off fresh `main`                                                                                                         |
| Fight entropy continuously                                                     | OpenAI, Fowler | ratchets that only shrink, Renovate, flaky quarantine, `repo-align` campaigns                                                                                   |

Two open problems are named by every source and apply to my setup too. **Behaviour verification** is the hardest category: a green gate proves maintainability, not that the feature does what the user needed, which is why acceptance criteria and human review stay in the loop. And **context is a budget**: every rule in standing context costs attention, so the harness must be pruned like code.

## Harness engineering, step by step

Treat the harness like a product: measure a baseline, change one thing, measure again, keep what helps. Without step 3 every later step is guesswork, which is exactly the trap METR's 19% result shows.

1. **Collect the failures.** Before building anything, gather what actually goes wrong: corrections you gave agents in the last few weeks, review comments, red CI runs, reverted PRs. Group them into classes (wrong scope, skipped tests, style drift, gamed checks, misunderstood ticket).
2. **Define done as a runnable check.** Write the gate the agent can run itself: build, types, tests, lint, security scan. If a class of failure can't be checked by a command, note it; it will need an inferential sensor or a human.
3. **Build the eval suite and record a baseline.** Turn 20 to 50 real failures into frozen tasks (see [Evaluating the harness](evaluating.md)) and run the current setup against them. This is the control every change is compared with.
4. **Place each rule in the strongest layer that can hold it.** Deterministic check, then hook, then skill, then instruction file, then memory. Pair each guide ("write the test first") with a sensor that notices when it was ignored ("no test file changed").
5. **Write sensor output for the agent.** Every failure message says what failed, why it matters, the deep fix, and the tempting shallow fix to avoid.
6. **Guard the guards.** Make weakening a rule, suppressing a warning, deleting a test or growing a baseline visible and human-approved. Agents optimise whatever is measured, including the measuring.
7. **Change one variable at a time.** A new hook, a rewritten `AGENTS.md`, a different skill: each is a PR, run against the eval suite, kept only if it improves the score without regressing anything.
8. **Ablate and prune.** Periodically remove a layer or an instruction and re-run. A rule whose removal changes nothing is costing context for no return; delete it.
9. **Promote what recurs.** A mistake seen twice becomes a check (`learn`). A capability task the agent now passes reliably graduates into the regression suite.
10. **Template and share.** Package the proven guides and sensors so every repo inherits them (Foundry's facades), versioned so teams can upgrade on their own schedule.

## Implementing custom harness elements, step by step

The ten steps above describe the loop. This section shows what building the individual harness elements looks like on a real repo. Mitchell Hashimoto's name for the habit is "engineer the harness": whenever an agent makes a mistake, build something so it can't make that mistake again, either a line in `AGENTS.md` or an actual tool. The running example is a PHP/Laravel service, but the method works for any stack.

### 1. Survey the stack and what already exists

Start from what the team already enforces, not from a blank page. Most of a harness already exists in the repo, partly wired up.

- **Stack:** languages, build tool, test runners, package managers, CI provider, and how a developer runs things locally.
- **Written rules:** linter and formatter configs (ESLint, PHPStan and PHP\_CodeSniffer sniffs, Roslyn analyzers and `.editorconfig`, Checkstyle), type-checker strictness, security scanners, coverage settings, CONTRIBUTING and PR templates.
- **Unwritten rules:** what reviewers keep saying. Mine the review history for them (Ivett Ördög's `build-project-review` does this), and mine git history for hotspots (`hotspot-rec`). These are the rules nobody has encoded yet.
- **Current state:** run every existing tool once and count the findings for each rule. That count becomes the baseline you ratchet down, and it shows which rules people already ignore.

The output is a flat list of rules. Each one is written as a plain sentence and has a source: a config file, a review thread or an incident.

### 2. Classify each rule by what can decide it

For each rule, ask these questions in order and stop at the first yes. The earlier the yes, the cheaper, faster and more trustworthy the check.

1. Can a command decide it with no false positives? Then it is a deterministic check, and it blocks.
2. Can a command decide most of it? Then it is still a deterministic check that blocks, but with an escape hatch that needs a label and a reason (a suppression, policed by `ruleset-guard`).
3. Is it a bounded judgment needed often and cheaply, such as on every tool call? A bounded judgment is a yes/no, a pick from a list, or a score. Then it goes to a decision model like Jev, which returns typed answers with probabilities. It runs as an advisory sensor with a tuned threshold. In my setup Jev does this in three places, all opt-in and off without an API key: tool-call triage at the end of a turn, a pre-filter that routes each diff hunk to the review lens that should look at it, and a `feature` pre-check that catches a diff that obviously misses an acceptance criterion before the full verify runs. None of them can pass or fail anything.
4. Does it need to read the ticket, the design or the wider change? Then it goes to an LLM reviewer before the PR, which is the `review` step inside `ship`. The reviewer runs in a fresh context, is advisory only, and ties every finding to a line and a concrete failure.
5. If none of these fit, it is a matter of taste or strategy. It goes to human review, and the rule lives in `AGENTS.md` as a guide.

| Rule (Laravel example)                                | Decided by                                                         | Placement                | Blocks?                          |
| ----------------------------------------------------- | ------------------------------------------------------------------ | ------------------------ | -------------------------------- |
| Code is formatted                                     | Pint or PHP-CS-Fixer                                               | in-loop on every edit    | fixed automatically              |
| Controllers never query the database directly         | Deptrac layer rule or a custom PHPStan rule                        | in-loop, gate and CI     | yes                              |
| No new complexity or duplication beyond today's level | habit-hooks sensor with a ratchet baseline                         | end of turn and gate     | yes, on growth only              |
| A bug fix comes with a regression test                | proxy check: source changed but no test changed                    | end of turn, then review | warns, then review               |
| A new route has authorization                         | proxy check: route without auth middleware; review covers the rest | gate and pre-PR review   | the proxy blocks; review advises |
| An agent's shell command is destructive               | decision model (Jev): yes/no with a probability                    | before each tool call    | advisory; escalates to a human   |
| User-facing error text does not leak internals        | decision model or LLM judge                                        | pre-PR                   | advisory                         |
| The change does what the ticket asked                 | LLM reviewer checking the acceptance criteria                      | pre-PR                   | advisory                         |
| The abstraction is right                              | a human                                                            | PR review                | the human decides                |

The bar comes from Google's years of experience with static analysis. Checks that break the build must produce no effective false positives. Checks shown during code review can tolerate up to about 10%. An effective false positive is any finding the developer chooses not to act on (Sadowski et al., CACM 2018). Models never get the blocking tier; that is "deterministic is the oracle" applied rule by rule.

Move rules into cheaper tiers over time. When the AI reviewer flags the same pattern a few times, write the lint rule and take that pattern off the reviewer's plate.

### 3. Place each check by its latency budget

The same rule runs in several places, and each placement has a time budget. A slow in-loop check gets bypassed. Simon Willison describes an agent as a loop of tools working toward a goal. The checks are the tools that tell the loop it has reached the goal, so they have to be fast enough to run inside it.

- **On every edit (about 1 to 2 seconds):** the formatter and single-file lint on the touched file, fixing automatically where possible.
- **Before tool calls (under a second):** decision-model triage of risky commands.
- **End of turn (under about 30 seconds):** typecheck, structural sensors on changed files, and the did-you-touch-a-test heuristics.
- **Pre-push and pre-PR (minutes):** the full gate, then the fresh-context AI review.
- **CI (as long as it takes):** the full gate again plus security scans and slower suites. CI is the source of truth.

### 4. Build every harness element test-first

A rule is code, and a rule that has never gone red has not proved it can catch anything. Each element gets fixtures before it is switched on.

- **Lint and analysis rules:** a red fixture (code the rule must flag) and a green fixture (similar code it must not flag). The tools support this directly: ESLint's `RuleTester` takes `valid` and `invalid` cases, Semgrep tests use `ruleid:` and `ok:` annotations, and PHPStan, Roslyn and ArchUnit all have test kits for rules.
- **Hooks:** feed recorded tool-call payloads into the script and assert the exit code and message. Include the cases where it should stay quiet.
- **Decision-model and AI-review sensors:** build a labelled set of positives, negatives and near misses, ideally with a second person labelling blind. Measure precision and recall, choose the threshold from those numbers, and pin the model version so a silent upgrade can't shift it. Hamel Husain's evals ladder fits here: cheap assertions first, then human and model review of real traces.
- **The gate itself:** plant a known violation on a throwaway branch and confirm CI goes red. A broken gate fails green, and nobody notices.

### 5. Roll out without regressing

1. **Shadow mode first.** Run the new check warn-only and log every firing to telemetry. Look at what it flagged and whether anyone acted on it.
2. **Baseline the legacy code.** Existing violations go into a ratchet baseline. The new rule then blocks new debt without blocking every PR on old debt.
3. **Run the harness eval before and after**, with one change per comparison (see [Evaluating the harness](evaluating.md)). Compare task pass rate, gate attempts per change, thrash in `loop-report`, and time and tokens spent.
4. **Make it blocking** only when a deterministic check reaches an effective false-positive rate near zero. A check that can't get there stays advisory.
5. **Watch the sensor's own numbers** after it ships: how often it fires, how often it is suppressed or overridden, and how much time it adds. A rising suppression rate means either the rule is wrong or its message is unclear.
6. **Make rollback cheap.** A check that lowers the eval score, or gets overridden more often than it helps, goes back to warn-only or gets deleted.

### 6. Keep it lean

Every quarter, run an ablation: switch off one rule, instruction or hook and re-run the eval. Delete whatever made no difference, because context and CI minutes are a budget. This follows Anthropic's advice to start simple and add complexity only when it demonstrably improves outcomes. It also follows their context-engineering advice to keep the agent's context to the smallest set of high-signal tokens. Each surviving rule then works as a fitness function, in the Building Evolutionary Architectures sense: an automated check that each change keeps the system moving toward its goals.

The same discipline applies to the codebase the harness protects. Kent Beck frames it as features versus futures: every feature spends some of the code's future optionality, and an agent left unchecked ships features fast enough that the codebase decays faster than ever. The work that restores optionality happens between features, in small, deliberate design steps before the next feature starts. In this setup the ratchets and the `repo-align` campaign are that step made routine: debt can only shrink, and tidying lands as its own small PR rather than riding along with a feature.

## Worked example: my harness

Everything above, applied. The agent half lives in [cmaintz-skills](https://github.com/CMaintz/cmaintz-skills) and the gate in [Foundry](https://github.com/CMaintz/foundry).

### The agent harness

The agent side has three layers, and the main design decision is which layer a rule goes in. Picking the wrong one is why most "AI coding standards" documents get ignored.

| Layer            | Mechanism                         | Character                                     | Example                                                      |
| ---------------- | --------------------------------- | --------------------------------------------- | ------------------------------------------------------------ |
| Reflex           | hooks                             | fires on its own, can block                   | "this function takes 7 parameters" before the agent may stop |
| Practice         | skills                            | invoked on demand, procedural, uses judgement | `ship`, `tdd`, `diagnosing-bugs`                             |
| Standing context | `AGENTS.md`, `CONTEXT.md`, memory | always loaded, shared vocabulary              | the domain model, team conventions                           |

#### Standing context: short, specific, enforceable

`AGENTS.md` is the canonical instruction file in each repo and `CLAUDE.md` is a one-line include of it, so Claude, Codex, Gemini and Cursor all read the same source. A global file holds my personal conventions across every project. They are written as rules with reasons, not aspirations. Examples from mine:

- **Tests:** a test earns its place by going red on a realistic bug. Write it first and watch it fail; a test that has never failed has not proved anything.
- **Comments:** say why, not what. History goes in the commit message, never the code.
- **Commits and PRs:** one logical change each, small and single-purpose, written like a human engineer. No AI attribution lines.
- **Working with me:** a question is a question. "Would X be better?" gets an answer, not an action.

#### Hooks: the rules an agent cannot forget

Hooks are small scripts the agent runtime fires at fixed moments. Placement follows cost: cheap checks run after every edit, slow ones once per turn.

| Hook                        | Fires                                                                       | What it does                                                                               | Blocks?          |
| --------------------------- | --------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------ | ---------------- |
| `auto-format`               | after every file edit                                                       | formats just that file (sub-second), so CI never fails on whitespace                       | no               |
| `habit-hooks-guard`         | when the agent tries to finish                                              | runs the repo's pinned structural-smell sensor on the changeset and coaches the agent      | yes, until fixed |
| `typecheck-stop`            | once per turn                                                               | runs the type checker if source changed                                                    | yes              |
| `guard-generated-files`     | before an edit or shell command                                             | stops the agent hand-editing debt baselines                                                | yes              |
| `guard-pr-create`           | before a shell command                                                      | blocks a bare `gh pr create`, so every PR goes through `ship`                              | yes              |
| `pre-push` (git)            | before `git push`                                                           | runs the full gate, so humans get the same check as agents                                 | yes              |
| Jev tool-call triage, Leash | end of turn (Leash also snapshots at session start and each prompt), opt-in | a cheap model flags destructive actions or broken un-lintable rules                        | never, warn only |
| `format-java-stop`          | once per turn                                                               | runs Spotless on Java files the turn touched (a JVM formatter is too slow to run per edit) | no               |
| `pre-commit` (git)          | before git commit                                                           | formats staged files with the repo's Prettier and re-stages them                           | no               |

#### Skills: procedures with judgement

Skills are reusable playbooks the agent loads when the task matches. My own set covers the delivery loop (`spec`, `feature`, `ship`, `review`, `pr-ci-watch`, `loop-report`, `repo-align`, `foundry-secret`, `codemap`). The broad practice layer comes from others, installed as plugins rather than copied so fixes flow in: Matt Pocock's skills (`tdd`, `diagnosing-bugs`, `codebase-design`, `domain-modeling`) and Ivett Ördög's (`learn`, `hotspot-rec`, `build-project-review`).

#### Codemap: a verified picture of the codebase

Without it, every session starts by re-reading the repo and guessing. The `codemap` skill writes a committed map instead, under `docs/codemap/`: an `INDEX.md`, one file per domain slice, and three lens files for the data model, integrations, and runtime and deploy. A deterministic census script lists manifests, entry points, schemas, env vars, churn and files that change together, and proposes slices from the directory layout and co-change. I confirm or edit the slice plan before any agent starts. Then one fresh agent per slice, plus one per lens, traces the main flows from entry point to persistence to side effects. Every claim must cite a file or `file#Symbol`, and anything it can't confirm becomes a question under "Unknowns". A verifier checks that every citation resolves and spot-checks at least five claims per file. Nothing is written until it passes, and a refuted claim is fixed or turned into a question. Each file is stamped with the commit it was checked against, and `codemap refresh` re-audits only the slices whose cited files changed since that stamp. On the Foundry side, `mise run codemap:check` confirms every citation in the map still resolves and prints how many commits each slice has fallen behind. It is advisory and deliberately kept out of the gate, so a drifting map warns rather than blocks. The map describes and never judges: smells and risks belong to `repo-align` and `hotspot-rec`. It lands as its own docs PR through `ship`.

The delivery skills read it. `spec` draws pointers from slice citations, edge-case questions from the traced side effects, and the scope-out from neighbouring slices. `feature` reads the slices its pointers touch before coding, and warns when a slice's cited files changed since its stamp, so the code wins over a stale map. `review` asks a question whenever a diff reaches into a slice the ticket never mentioned. In a repo without a codemap, all three skip this step.

#### Memory and the `learn` flywheel

At the end of a session, the `learn` skill reflects on what went wrong or right and routes each lesson to the strongest place that can hold it, in this order:

1. a deterministic hook or check, so the mistake becomes impossible
2. `AGENTS.md` / `CLAUDE.md`, so it becomes standing context
3. a new skill, so it becomes a procedure
4. auto-memory, as a last resort

That ordering is the whole thesis in one list: prefer the placement that makes a mistake impossible over the one that reminds you not to make it. My memory store holds about 25 short facts, one per file, such as "local main is often stale, fetch before branching" or "a gate change must be run before it ships, because a broken gate fails green".

### Foundry: the shared gate

Foundry is a set of reusable CI workflows, task templates and config presets that every repo inherits, so one quality bar applies across TypeScript, Java, PHP, .NET, Python and Kotlin. It answers one question for humans and agents alike: when is a change done?

#### Six verbs, one interface

```
mise run fix        # auto-fix what is mechanically fixable
mise run lint       # style + structural smells
mise run typecheck  # static types
mise run test       # tests + coverage floor
mise run audit      # vulnerabilities, secrets, static security analysis
mise run gate       # all of the above, in order. The oracle.
```

Everything else (CI, git hooks, skills) calls verbs, never tools. A skill says `mise run lint`, never `eslint` or `phpstan`. That one indirection is why a single skill library serves a React repo and a Java repo. `mise` also pins every tool version, so a laptop and the CI runner can't disagree.

#### Same rules, three placements

| Placement | When                           | Feedback goes to     | What runs                                   |
| --------- | ------------------------------ | -------------------- | ------------------------------------------- |
| In-loop   | while the agent edits          | the agent, mid-task  | formatter, type check, smell sensor (hooks) |
| Pre-push  | before code leaves the machine | the developer        | the full `mise run gate`                    |
| CI        | every pull request             | the permanent record | the same gate, plus security guards         |

CI is deliberately 100% deterministic: no model and no API key. Agent work runs locally, inside a session that is already paid for, before the PR exists. That also removes the riskiest combination in CI security: a model holding a key and write access on a branch an agent wrote.

The rule is itself a test. A boundary test fails the build if any gate workflow or verb calls the advisory model layer, so a model can never end up deciding pass or fail. The gate may run that layer's own unit tests, but never call it for a verdict.

#### Ratchets: debt can shrink, never grow

Existing violations are recorded in committed baseline files (ESLint's built-in suppressions, the habit-hooks snooze list). Coverage floors are set to today's real number and may only rise. Fixing an old problem removes it from the baseline for good, and an automated job opens a PR whenever the baseline shrinks. A floor you can't meet is a floor you'll delete, so the bar starts where the code actually is.

#### Structural smells with coaching

[habit-hooks](https://github.com/habit-hooks/habit-hooks) wraps per-language detectors and maps them onto language-independent smells: oversized file, oversized function, too many parameters, high complexity, deep nesting, duplication, dead code. When it fails it coaches the agent, and the coaching argues against mechanical compliance: splitting a file at line 200 into `foo-1.ts` and `foo-2.ts` satisfies the threshold while leaving the real problem in place. I built and published the .NET sensor for it myself.

#### `ruleset-guard`: the anti-gaming control

A ratchet only sees what the tool reports, so the cheapest way to beat it is to switch the tool off. `ruleset-guard` runs on every PR and blocks, unless a human adds a label and writes the reason in the PR body:

- a change to a rule config, threshold or workflow in the same PR as source code
- a new in-source suppression (`eslint-disable`, `@ts-ignore`, `@SuppressWarnings`, `# noqa`)
- a config demotion (`"strict": false`, a severity set to none)
- a deleted or skipped test
- a debt baseline that grew

It is tightening-aware: making the gate stricter never needs a label, only loosening does.

#### The rest of the CI estate

- **Security facade:** secret scanning over full history (gitleaks), the guard above, and diff-aware static analysis (Semgrep) that only flags new findings.
- **Supply chain:** every action and tool pinned by version or commit SHA; Renovate opens the update PRs.
- **Speed:** superseded runs cancel themselves, and a monorepo classifier rebuilds only the packages a PR touched. One always-running aggregate check (`gate-ok`) is what branch protection requires, so skipped jobs never wedge a merge.
- **Autofix on a label:** adding the `autofix` label to a red PR makes CI run `mise run fix`, commit the result to the branch and drop the label. It runs only on same-repo PRs, never on forks.
- **Releases:** one script cuts a semver tag from conventional commits and refuses a non-major bump if it sees a breaking change. Consumers pin `@v2` and ride non-breaking updates.
- **Backport discipline:** anything non-language-specific built in a consumer repo comes back to Foundry the same session, so every repo benefits.
- **Dogfooding:** the harness repos use their own gate. Each has a root `mise.toml` with the six verbs, the same `mise run gate` runs locally and in CI (`gate.yml` in cmaintz-skills, `self-gate.yml` in Foundry), and branch protection requires it before anything merges. So my own tickets go through `feature` and `ship` like anyone else's.

## Applying it to a TypeScript serverless team

My own setup grew around one person working across many stacks, so parts of it exist for problems a single-stack team doesn't have, and a team on TypeScript, Lambda and DynamoDB has problems my setup never had to solve. This is how I'd approach that team's harness with everything I've learned, rather than copying mine.

### What carries over unchanged

- **The beliefs.** The model proposes, deterministic checks decide. Ratchet, don't wall. Guard the guards. Reviewers advise, never block.
- **The six verbs and three placements.** `fix`, `lint`, `typecheck`, `test`, `audit` and `gate`, running the same checks in the agent's loop, before push and in CI.
- **The ticket as the real prompt,** with acceptance criteria and a Definition of Done, owned by the product owner.
- **The ticket-to-PR loop,** the fresh-context review before the PR, and `learn` turning repeated mistakes into checks.
- **The evaluation method.** Measure a baseline, change one thing, measure again.

### What I'd simplify

- **One stack, one preset.** Foundry carries presets for six languages; this team needs one strict TypeScript preset (typed ESLint rules, Prettier, strict `tsconfig`, Vitest), owned in one place and versioned like a library.
- **Fewer moving parts in the agent half.** The skills and hooks that matter are the loop (`spec`, `feature`, `ship`, `review`), the formatter and smell hooks, and the PR guard. I'd start there and add the rest only when a measured problem asks for it.

### What I'd add for serverless

The biggest difference is that a Lambda function is mostly wiring: most of what can go wrong lives at the boundaries (events, permissions, the data model, the cloud itself), not in the function body. So the harness has to reach those boundaries.

- **Thin handlers, testable core.** Business logic lives in plain TypeScript modules; the Lambda handler only parses the event, calls the core and shapes the response. Agents get fast unit tests on the core, and the handler stays too thin to hide logic. This is a structural rule the smell sensor and an architecture check can enforce.
- **Schemas at every boundary.** API Gateway payloads, EventBridge and SQS messages, and DynamoDB items are validated against shared schemas (for example zod) in one place. Contract tests between services (Pact, or schema snapshot tests for events) catch the change that compiles but breaks a consumer.
- **The data model as executable access patterns.** With single-table DynamoDB design, the access patterns are the schema. Each one gets an integration test against DynamoDB Local, so an agent refactoring keys or indexes finds out in the loop, not in production.
- **Infrastructure in the gate.** The IaC (CDK, SAM or SST) is synthesised and checked on every change: `cdk synth` plus cdk-nag or cfn-lint for misconfigurations, and a bundle-size ratchet per function so cold starts can't creep up unnoticed.
- **Guard IAM like lint rules.** `cdk diff --security-only --fail` fails when a change broadens IAM permissions or network access. That is the same anti-gaming control as `ruleset-guard`: allowed, but only with a human label and a reason, because "grant `*`" is exactly the shortcut an agent takes to make an error go away.
- **Executable acceptance tests against a real stack.** This is where Farley's argument gets a proper runner. Every PR deploys an ephemeral preview stack to a sandbox account, the Given-When-Then acceptance tests run against it, and it is torn down on merge. Unit tests prove the logic; the acceptance suite proves the deployed system does what the ticket asked.
- **Observability the agent can read.** Powertools for AWS Lambda gives structured logs, traces and metrics. Pointing the agent at the preview stack's logs turns "it fails in AWS" from a guess into a sensor.

### Credentials and blast radius

My CI runs with no model and no cloud keys. A serverless team's CI must deploy, so the rule becomes: no long-lived keys anywhere. CI assumes a short-lived, least-privilege role through GitHub OIDC, scoped to the sandbox account for preview stacks and to a separate, human-approved path for production. Agents get the sandbox account only, and a deterministic hook denies any deploy or AWS CLI call that targets another profile. A decision model like Jev can still triage risky commands, but the hard stop is the hook and the IAM boundary.

### Where a team needs more than I do

- **Shared ownership.** Per-service `AGENTS.md` files and CODEOWNERS, reviewed like code, so standing context doesn't turn into one person's preferences.
- **Team-level metrics.** The DORA measures (lead time, deployment frequency, change failure rate, time to restore) alongside gate rounds and escaped defects, compared for agent-authored and human-authored PRs. That is how the team learns whether the harness helps, rather than whether it feels like it does.
- **One open decision: AI review in CI.** I keep model review local, before the PR, so CI stays deterministic and keyless. A team may want a shared review bot on every PR instead. It is a reasonable choice, as long as it stays advisory and its key is scoped to that one job.

### Where I'd start

A pilot with one team and one service, in this order: the gate with baselines, the ticket template, the formatter and PR hooks, then the ticket-to-PR loop, and only then preview stacks and acceptance tests. Measure gate rounds and escaped defects from the first week, and run the evaluation suite before and after each harness change.

## Sources

- InfoQ, [OpenAI's harness engineering with Codex](https://www.infoq.com/news/2026/02/openai-harness-engineering-codex), February 2026 (summary of [OpenAI's post](https://openai.com/index/harness-engineering/))
- Anthropic, [Best practices for Claude Code](https://code.claude.com/docs/en/best-practices)
- Google DORA, [State of AI-assisted Software Development 2025](https://dora.dev/dora-report-2025/), with the [InfoQ summary](https://www.infoq.com/news/2025/09/dora-state-of-ai-in-dev-2025)
- METR, [Measuring the Impact of Early-2025 AI on Experienced Open-Source Developer Productivity](https://metr.org/blog/2025-07-10-early-2025-ai-experienced-os-dev-study/), July 2025
- Mitchell Hashimoto, [My AI Adoption Journey](https://mitchellh.com/writing/my-ai-adoption-journey), 5 February 2026 (step 5, "Engineer the Harness")
- Anthropic, [Building effective agents](https://www.anthropic.com/engineering/building-effective-agents), 19 December 2024
- Anthropic, [Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents), 29 September 2025
- Simon Willison, [Designing agentic loops](https://simonwillison.net/2025/Sep/30/designing-agentic-loops/), 30 September 2025
- Sadowski, Aftandilian, Eagle, Miller-Cushon and Jaspan, [Lessons from Building Static Analysis Tools at Google](https://research.google/pubs/lessons-from-building-static-analysis-tools-at-google/), Communications of the ACM, April 2018
- Neal Ford, Rebecca Parsons and Patrick Kua, Building Evolutionary Architectures (O'Reilly), and Thoughtworks, [How fitness functions can help us govern and measure AI](https://www.thoughtworks.com/en-ca/insights/podcasts/technology-podcasts/how-fitness-functions-help-govern-measure-ai), 6 March 2025
- Hamel Husain, [Your AI Product Needs Evals](https://hamel.dev/blog/posts/evals/), 29 March 2024
- [ESLint RuleTester](https://eslint.org/docs/latest/integrate/nodejs-api#ruletester) and [Semgrep: Testing rules](https://semgrep.dev/docs/writing-rules/testing-rules)
- TypeSafe, [System One models and Jev](https://docs.typesafe.ai/concepts/system-one)
- AWS, [cdk diff](https://docs.aws.amazon.com/cdk/v2/guide/ref-cli-cmd-diff.html) (`--security-only`, `--fail`), [cdk-nag](https://github.com/cdklabs/cdk-nag) and [cfn-lint](https://github.com/aws-cloudformation/cfn-lint)
- AWS, [DynamoDB Local](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/DynamoDBLocal.html) and [Powertools for AWS Lambda (TypeScript)](https://docs.powertools.aws.dev/lambda/typescript/latest/)
- GitHub, [Configuring OpenID Connect in Amazon Web Services](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/configuring-openid-connect-in-amazon-web-services)
- [Pact](https://docs.pact.io/): consumer-driven contract testing

---

**Next:** [Evaluating the harness](evaluating.md). How to measure whether any of this actually helps.
