# Evaluating the harness

[Start](README.md) > [Working with agents](workflow.md) > [Building a harness](building-a-harness.md) > **Evaluating the harness**

A harness benchmark answers one question: does this version of our setup make agents produce more correct, safer work on our code, at an acceptable cost? Hold the model fixed and vary the harness, so a score change can be attributed to the harness. Public benchmarks are a sanity check; decisions come from a custom suite built from your own repos.

### Design principles

These follow Anthropic's [guide to agent evals](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents) (January 2026) and what I used in my own [classifier-bench](https://github.com/CMaintz/classifier-bench), a frozen 2,321-case benchmark with confidence intervals where a blind second annotator agreed on 431 of 434 authored labels.

- **Real tasks, frozen.** Tasks come from your own bug tracker, reverted PRs and review comments, pinned to a commit. 20 to 50 is a good start; as a rule of thumb, aim for around 100 to detect smaller differences.
- **Unambiguous with a reference solution.** Two experts should agree on pass or fail. A task nobody passes is usually a broken task, not a weak agent.
- **Grade outcomes, not paths.** Check the final state (hidden tests pass, file exists, bug gone), not the exact sequence of tool calls.
- **Clean environment per trial.** Fresh container or worktree; no shared caches or git history from earlier trials, which agents have been seen to exploit.
- **Several trials per task.** Agents are non-deterministic; run 3 to 5 trials and report reliability, not one lucky run.
- **Balanced.** Include tasks where the agent should act and where it should not: a question that must not trigger code changes, a ticket that must be refused as unclear, a test that must not be deleted.
- **Hidden from the agent.** Grading tests and reference solutions live outside the workspace, so the agent can't read or edit them.
- **Read transcripts.** Sample about 10% of trials by hand to catch graders rejecting valid solutions or passing gamed ones.

### Task categories and suggested weights

The weights reflect where a team's agent time goes and where mistakes are expensive; tune them to your own work mix.

| Category                 | Weight | Example task                                                                        | Primary grader                                                                     |
| ------------------------ | ------ | ----------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------- |
| Bug fix from an issue    | 20%    | reproduce and fix a reported defect                                                 | hidden fail-to-pass tests + existing tests still pass                              |
| Feature from a ticket    | 20%    | implement a small feature with acceptance criteria                                  | hidden acceptance tests + green gate                                               |
| Guardrails and restraint | 15%    | a tempting shortcut: failing test, strict lint rule, injected instruction in a file | deterministic diff checks: no suppression, no deleted test, no out-of-scope action |
| Refactor                 | 10%    | split a god class without changing behaviour                                        | all tests pass + structural-smell count drops                                      |
| Debugging and diagnosis  | 10%    | find the root cause of a flaky or slow test                                         | named cause matches reference + a failing repro test                               |
| Codebase analysis        | 10%    | "how does auth refresh work, and where would X go?"                                 | rubric against a reference answer, calibrated model judge                          |
| Code review              | 5%     | review a diff with seeded bugs                                                      | recall of seeded bugs and precision (false alarms)                                 |
| Research                 | 5%     | answer an API or library question from docs                                         | claims supported by cited sources, version correct                                 |
| Spec and ticket writing  | 5%     | turn a vague request into a ticket                                                  | rubric: testable criteria, scope, out-of-scope, open questions                     |

### Scoring a single trial

Each trial gets a quality score from weighted dimensions, then two hard gates:

| Dimension            | Weight | How it is measured                                                                    |
| -------------------- | ------ | ------------------------------------------------------------------------------------- |
| Correctness          | 50%    | hidden tests or rubric; partial credit for multi-part tasks                           |
| Gate compliance      | 15%    | full `mise run gate` green from a clean tree                                          |
| Scope discipline     | 10%    | files touched vs the reference set; diff size vs the reference diff                   |
| Honesty and evidence | 10%    | every claim ("tests pass") matches what actually happened; evidence shown             |
| Code quality         | 10%    | smell delta, duplication, function size, naming judged against the repo's conventions |
| Process              | 5%     | test written before the fix, own branch or worktree, conventional commit              |

```math
\text{trial score} = \text{safety} \times \text{honesty gate} \times \sum_i w_i \, s_i
```

Safety is 0 if the trial did anything forbidden (suppressed a check to pass, deleted or skipped a test, ran a destructive command, followed an injected instruction), else 1. The honesty gate is 0.5 if the agent claimed success that the grader disproves, else 1. Making these multipliers rather than weights means no amount of quality buys back an unsafe or dishonest run.

### What to report

- **Reliability:** pass@1, plus pass^k (all k trials succeed). pass@k (at least one of k) flatters; for a team relying on agents, pass^k is the honest number. At 75% per trial, pass^3 is about 42%.
- **Category scores,** never only the weighted total, so a gain in features can't hide a loss in guardrails.
- **Efficiency, kept separate from quality:** tokens and cost, wall-clock time, turns, gate rounds to green, and human interventions. The headline is cost per solved task.
- **Uncertainty:** paired comparisons per task between harness A and B, with bootstrap confidence intervals. A change inside the interval is noise, not progress.
- **Regressions:** the regression suite (tasks the agent used to pass) should sit near 100%; any drop blocks the harness change.

### Useful heuristics and detectors

- **Gaming detector:** grep the diff for new suppressions, skipped or deleted tests, loosened thresholds, and code that special-cases test inputs.
- **Claim checker:** parse the agent's final message for claims (tests pass, build green, file updated) and verify each against the environment.
- **Scope ratio:** files touched divided by files in the reference fix; above about 2 suggests scope creep.
- **Thrash count:** a check that passed, then failed after a later edit. Rising thrash means the feedback is confusing the agent.
- **Question restraint:** for a pure question task, any file change is a failure.
- **Model-judge calibration:** compare a model grader to human grades on a sample; keep it only with high agreement, and give it an "unknown" option instead of forcing a verdict.

### Switch-off tests: what each layer is worth

Run the same suite with one layer switched off at a time: no hooks, no `AGENTS.md`, no skills, no fresh-context review, no gate access. The score drop per layer is its measured value, and a layer with no drop is a candidate for removal.

### Third-party options

| Option             | What it measures                                                            | Use it for                                                                                                                                                                                                                  |
| ------------------ | --------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| SWE-bench Pro      | fixing real GitHub issues against hidden tests, with a held-out private set | a sanity check that the harness doesn't hurt general bug fixing                                                                                                                                                             |
| Terminal-Bench 2.0 | multi-step tasks in a terminal                                              | tool use and environment handling                                                                                                                                                                                           |
| SWE-bench Verified | the older issue-fixing set                                                  | avoid for decisions: OpenAI stopped reporting it, citing contamination and scaffolding confounds ([guide](https://codex.danielvaughan.com/2026/06/17/benchmark-literacy-guide-reading-coding-agent-benchmarks-critically/)) |

Public scores move by several points with the harness alone (one report shows three agents on identical model weights spanning 50.2% to 55.4% on SWE-bench Pro), so only compare scores run on the same harness and benchmark version ([benchmark literacy guide](https://codex.danielvaughan.com/2026/06/17/benchmark-literacy-guide-reading-coding-agent-benchmarks-critically/)).

### Running it

- **On every harness change:** the suite runs on the PR that changes a hook, skill or instruction file, and posts the score diff as a comment, the same way debt baselines are reported.
- **On a schedule:** weekly against the current model and harness, to catch drift when a model or tool updates underneath you.
- **In production:** the real eval is delivery. Track change failure rate, reverted PRs, review rework and escaped defects for agent-authored PRs versus human ones. If the suite improves and these don't, the suite is measuring the wrong thing.

## Data and feedback

The system measures itself with deterministic, local data, so that improving the harness is driven by evidence rather than by how a session felt. No dashboard costs CI minutes; the data sits next to the code.

| Signal                | Where it comes from                                                                      | What it tells you                                                                                                                      |
| --------------------- | ---------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| Loop telemetry        | every gate verb appends one line (verb, scope, placement, exit code, duration) to a local log | how many gate rounds a change took, which verb eats the time, and **thrash**: a check that passed, then failed again after a later fix |
| Debt baselines        | committed suppression and snooze files                                                   | whether debt is actually shrinking; a CI comment shows how each baseline moved in the PR                                               |
| Flaky-test quarantine | a baseline of known flaky tests, plus a rerun classifier                                 | flake vs real failure; a quarantined test leaves the list after enough consecutive greens                                              |
| Prompt-output evals   | scored fixtures of good and weak AI outputs                                              | whether a prompt change made output quality worse, asserted on the ranking of good above weak                                          |
| Architecture fitness  | dependency rules (dependency-cruiser, ArchUnit, import-linter) with frozen baselines     | whether layering and dependency direction still hold                                                                                   |
| Git history           | hotspot and change-coupling analysis                                                     | where maintenance cost really lives, so refactoring targets the files that change most                                                 |

Two principles govern this data. First, telemetry never changes an outcome: if logging fails, the verb's own exit code still wins. Second, evals ratchet like any other baseline: adding a fixture is free, removing one counts as loosening the gate and needs a human label.

The feedback reaches the system through `learn` (lessons become hooks or rules), `loop-report` (a short verdict: converging or thrashing, what's slow, the next action), and `hotspot-rec` (one design improvement grounded in git history). Telemetry is written by `foundry-verb-wrap` on every gate verb, and the flaky classifier is `foundry-flaky`, which reruns failures; its `prune` command re-arms a quarantined test after 10 consecutive greens.

## Sources

- Anthropic, [Demystifying evals for AI agents](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents), 9 January 2026
- Daniel Vaughan, [Benchmark literacy: reading coding agent benchmarks critically](https://codex.danielvaughan.com/2026/06/17/benchmark-literacy-guide-reading-coding-agent-benchmarks-critically/), June 2026
- [classifier-bench](https://github.com/CMaintz/classifier-bench): my own benchmark, as a worked example of the method
- Hamel Husain, [Your AI Product Needs Evals](https://hamel.dev/blog/posts/evals/), 29 March 2024

---

That's the end. Back to the [start](README.md), or go straight to the code: [Foundry](https://github.com/CMaintz/foundry) and [cmaintz-skills](https://github.com/CMaintz/cmaintz-skills).
