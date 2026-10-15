# LinkedIn post — Foundry

LinkedIn strips markdown, so the copy below is plain text by design: blank lines
and dashes carry all the structure. Paste as-is, attach `foundry-linkedin-deck.pdf`
as a document post (it renders as a swipeable carousel).

---

## Main version (~2,600 chars — LinkedIn's limit is 3,000)

My agent fixed the same function four times, and the net change was nothing.

The local hook flagged it as too long, so it split it. CI flagged the result as too complex — a rule the local hook never ran — so it inlined the branch back. Then the local hook flagged it as too long again.

That wasn't the agent being dumb. It optimised exactly what it was shown, and it was shown two different rule sets.

I'd been building two separate things: a CI pipeline, and a set of "AI coding standards" in CLAUDE.md. They were never going to agree — and the prose half decayed inside a single session anyway, followed early and quietly ignored by the end.

So I rebuilt them as one rule set in three placements: in the agent's loop while it edits, before the push, and on the PR. Behind one narrow interface of six verbs — fix, lint, typecheck, test, audit, gate. Callers invoke verbs, never tools. A skill says "mise run lint", never "eslint". That single indirection is the only reason one skill library can serve a Kotlin repo and a React one.

Two rules do most of the work.

Deterministic is the oracle; probabilistic only proposes. Linters, types, tests and scanners decide pass/fail. A model produces a patch, and the patch is accepted only if the gate then passes from a clean tree. A model's claim that it fixed something isn't evidence. The exit code is.

Ratchet, don't gate. Point a good linter at an existing codebase and everything is red on day one, so you turn it off in week two. Record today's violations as a baseline that may only ever shrink instead. New code gets the full standard, legacy gets "no worse".

What I got wrong:

I shipped thresholds without their reasons. The smell gate flagged long functions, so the agent made functions short — every coherent step became a two-line helper. Technically green, measurably worse to read. I'd traded one real problem for a pile of incohesive fragments.

The fix wasn't a looser number. It was writing down what the number is for: cohesion is the goal, and length and complexity are just the honest signals that you don't have it. A threshold with no stated rationale will be optimised against — by an agent, and eventually by me.

The cheaper mistake: I spent real time designing a baseline mechanism that ESLint and the smell sensor had both already shipped. Check whether the ratchet exists before you hand-roll one.

The deck walks through the whole thing, including five CI gotchas that cost me real time. My favourite: a required check that gets path-filtered out never reports at all. It just sits on "Expected" and the PR can never merge.

Both halves are MIT.
CI half → github.com/CMaintz/foundry
Agent half → github.com/CMaintz/cmaintz-skills

#AIAgents #DeveloperExperience #CICD #SoftwareEngineering

---

## Short version (~950 chars) — if you'd rather let the deck carry it

My agent fixed the same function four times, and the net change was nothing.

The local hook said it was too long, so it split it. CI said the result was too complex — a rule the local hook never ran — so it inlined the branch back. Then the local hook said it was too long again.

That's not the agent being dumb. It optimised exactly what it was shown, and it was shown two different rule sets.

I'd built a CI pipeline and a set of "AI coding standards" as two separate things. So I rebuilt them as one rule set in three placements — in the agent's loop, before the push, and on the PR — behind six verbs that every repo implements the same way.

Two rules carry it: the deterministic gate is the only thing allowed to decide "done", and the baseline of accepted debt may only ever shrink.

Deck has the full design, plus the threshold I had to walk back when the agent optimised against it.

github.com/CMaintz/foundry — MIT

#AIAgents #DeveloperExperience #CICD

---

## Notes before you post

- **The opening is a composite.** "Four commits, net change nothing" dramatises the
  fix-thrash you confirmed; swap in a real instance if you have one to hand — it'll
  land harder and you won't have to hedge.
- **Slide 11, item 04** quotes the real 20.0s → 2.6s jsdom number from the pilot.
  Everything else avoids figures rather than invent them.
- First comment is a good place to drop the OVERVIEW.md link, since LinkedIn
  suppresses posts with outbound links in the body. The repo URLs in the body are
  plain text, not links, so they're safe.
