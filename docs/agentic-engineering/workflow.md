# Working with agents

[Start](README.md) > **Working with agents** > [Building a harness](building-a-harness.md) > [Evaluating the harness](evaluating.md)

## Prompting and working practices

The biggest prompting lever is not phrasing; it is giving the agent a target it can check itself against. A prompt with a runnable definition of done beats a clever prompt every time.

### Prompting

- **Give a verifiable target.** "Make `mise run gate` green and satisfy these three acceptance criteria" converges. "Clean this up" wanders.
- **Spec before code.** The `spec` skill turns a rough idea into a ticket through a short back-and-forth: intent, an acceptance-criteria checklist, scope boundaries and pointers to the relevant code (each checked to exist in the tree), plus a Definition of Done (below). Product owners can write these; agents can claim them.
- **Done means more than behaviour.** Every ticket carries a Definition of Done next to its acceptance criteria: the non-behavioural conditions this ticket needs and the pipeline doesn't already check, such as a migration with a working down step or updated docs. Anything the gate or `ship` already enforces stays out. If the criteria already say it all, the DoD is the single line "None beyond the acceptance criteria." A ticket without one can't be claimed. `spec` drafts it with you, `feature` checks every item, and `review` holds the diff to it.
- **Separate questions from instructions.** "Would X be better?" should get an answer, not a code change. Stating this explicitly in standing context removes a whole class of surprise edits.
- **Brief sub-agents like a new colleague.** A sub-agent knows only its prompt: state the goal, what is already ruled out, which files to read, and the narrow scope. If you can't write the brief, you don't understand the task yet.
- **Ask for the finding, not the hypothesis.** Hand an agent your theory and it tends to confirm it. For verification, ask a fresh agent to refute the claim.
- **Put rules in the strongest layer.** If you find yourself repeating an instruction in prompts, it belongs in `AGENTS.md`. If it keeps being ignored there, it belongs in a hook.
- **Write for agents tersely.** Instruction files work best short and specific: rules with a one-line reason, examples of the boundary, no motivational prose. Long files dilute the rules that matter.

### Acceptance tests as the contract

The practice I lean on hardest follows Dave Farley's case for acceptance-test-driven development with AI. Natural language is too loose to specify software on its own, and vague prompts produce vague software. So the acceptance criteria stop being prose and become executable.

- **Contracts beat vibe coding.** Each acceptance criterion is written as a Given-When-Then scenario and backed by a test that proves it. It is the contract the agent works to, and a fitness function in the evolutionary-architecture sense: the change either passes it or it doesn't.
- **Executables as prompts.** Scenarios written in a small domain-specific language for the product are the most precise prompt there is. "Given a customer with an expired card, when they renew, then they are sent to update their payment details" leaves the agent nothing to guess.
- **Behaviour over boilerplate.** Nobody reads compiler output any more; we check that the program behaves. Review shifts the same way: people read the specifications and the design, and the pipeline proves the generated code meets them, instead of humans auditing every line.
- **Autonomy earned one passing spec at a time.** An agent can loop against the acceptance suite on its own, and trust grows with each scenario it turns green. The guardrails make that safe: the gate, the ratchets and `ruleset-guard` stop it passing by drifting, weakening tests or piling up debt.

In my loop, `spec` pushes every acceptance criterion towards something observable with the product owner: an input, an action, an expected result, machine-checkable where possible. Given-When-Then is the shape I write them in. `feature` implements against that checklist, loops the gate to green, then walks every criterion and every Definition of Done item and reports each as pass or fail. The fresh-context review checks the diff against the same list. Writing the failing test first is a standing rule and the `tdd` skill's job, so each criterion becomes executable through the test that proves it.

### What a ticket looks like

Every ticket is a GitHub issue with five required fields, defined by Foundry's ticket schema and enforced by an issue form:

| Field               | What it holds                                                      | Why it matters                                                    |
| ------------------- | ------------------------------------------------------------------ | ----------------------------------------------------------------- |
| Intent              | the what and why, in a sentence or two                             | the fresh-context reviewer checks the diff against it             |
| Acceptance criteria | a checklist; every item verifiable, ideally executable             | the load-bearing field: no checklist, no claim                    |
| Definition of Done  | non-behavioural done-conditions the pipeline doesn't already check | catches the migration without a down step, the doc nobody updated |
| Scope boundaries    | explicit "do not touch X"                                          | guards against silent scope creep                                 |
| Pointers            | files, modules or prior art to start from                          | saves the agent from guessing where to look                       |

Labels move it through a small state machine: `agent:ready` (only after the owner approves the whole ticket), `agent:working` (one per worker at a time) and `agent:blocked` (escalated, with the reason posted on the issue). An example:

```markdown
## Intent

As a customer whose card has expired, I want to be sent to update my
payment details when I renew, so my subscription doesn't lapse silently.

## Acceptance criteria

- [ ] Given a customer with an expired card, when they click Renew,
      then they are sent to the update-payment page and nothing is charged.
- [ ] Given a customer with a valid card, when they click Renew,
      then the renewal is charged and confirmed as it is today.
- [ ] Given the payment provider is down, when a customer renews,
      then they see a retry message and no charge is made.

## Definition of Done

- [ ] Support has approved the wording of the expired-card message.
- [ ] The runbook entry for failed renewals is updated.

## Scope boundaries

- Do not change the pricing or plan-selection screens.
- Do not touch the payment provider client beyond reading card expiry.

## Pointers

- app/Http/Controllers/RenewalController.php
- app/Services/Billing/ (the existing charge flow)
- codemap slice: billing
```

### Working discipline for a team

- **One agent, one worktree, one branch, one PR.** Parallel sessions on one checkout interleave commits and poison both PRs. Every code-editing agent gets its own git worktree off fresh `main`.
- **Bounded loops.** The feature driver retries the gate at most 5 times and bails after two rounds without progress, posting the stuck state to the ticket. An agent that can loop forever will.
- **Green is not correct.** After the gate passes, the agent checks the result against the ticket's acceptance criteria and Definition of Done, then a fresh-context reviewer checks it again.
- **Stop and surface, don't weaken.** If the only path to green is disabling a check, the agent stops and reports. That decision belongs to a human.
- **Delegate reading, keep deciding.** The main thread orchestrates; sub-agents do the wide reading and return conclusions, not file dumps.
- **Small PRs, human-style writing.** Refactors apart from behaviour changes. Commit messages and PR descriptions short and plain, so reviewers actually read them.
- **Scale verification to risk.** A typo fix gets the gate and a PR. A change to the gate itself gets run end-to-end before it ships, because a broken gate fails silently green.

## Rolling this out to a team

Adopt it in five stages, each useful on its own, and move on only when the previous stage is trusted. Starting with autonomous agents before the gate exists is the most common way teams end up with more output and more incidents, the pattern DORA describes.

1. **One gate, everywhere.** Agree the verbs and wire the same checks into local runs and CI. Baseline today's violations so nothing goes red on day one. Success: nobody hears "passes locally, fails in CI" any more.
2. **Shared standing context.** One short `AGENTS.md` per repo with build commands, conventions and gotchas, reviewed like code. Success: agents stop asking questions the file already answers.
3. **Reflex hooks.** Formatter after each edit, the smell and type checks before the agent may stop, the full gate before push, guards on debt baselines and PR creation. Success: rules that used to be repeated in prompts are now enforced.
4. **The ticket-to-PR loop.** Product owners and developers write tickets with acceptance criteria; agents claim them, loop to green, verify, and open PRs through one sanctioned path. Humans review every PR. Success: tickets that meet the template get a reviewable PR without hand-holding.
5. **Measure and improve the harness.** Track gate rounds per change, thrash, review findings and escaped bugs. Run `learn` at session ends so each recurring mistake becomes a check. Success: the same mistake doesn't reach review twice.

### Where a product owner fits

- **Owns the intent.** The ticket is the agent's real prompt. Clear acceptance criteria, explicit out-of-scope, and an example of done do more for output quality than any prompting trick.
- **Approves the ticket before any agent starts.** `agent:ready` goes on only after the owner explicitly approves the full ticket, Definition of Done included; a vague "looks fine" doesn't count. `feature` then walks every DoD item as well as every acceptance criterion and reports each one as pass or fail.
- **Owns behaviour verification.** The gate proves the code is maintainable and safe; it can't prove the feature solves the user's problem. That judgement stays human.
- **Can read the loop.** Ticket labels (`agent:ready`, `agent:working`, `agent:blocked`) and the stuck-state notes an agent posts make progress and blockers visible without a standup.

### Guardrails worth keeping from day one

- No model in CI and no API keys there; agent work happens locally, before the PR.
- No agent can weaken a rule, suppress a check or delete a test without a human label and a written reason.
- Every agent works in its own worktree and branch; one PR per concern.
- Reviews by AI are advisory; merges need human approval and green required checks.

## Sources

- Anthropic, [Best practices for Claude Code](https://code.claude.com/docs/en/best-practices)
- Google DORA, [State of AI-assisted Software Development 2025](https://dora.dev/dora-report-2025/), with the [InfoQ summary](https://www.infoq.com/news/2025/09/dora-state-of-ai-in-dev-2025)
- METR, [Measuring the Impact of Early-2025 AI on Experienced Open-Source Developer Productivity](https://metr.org/blog/2025-07-10-early-2025-ai-experienced-os-dev-study/), July 2025

---

**Next:** [Building a harness](building-a-harness.md). The method behind the tooling, and my own harness as a worked example.
