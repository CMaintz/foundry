# Code standards — a function does one thing

Copy the relevant lines into your repo's `AGENTS.md` / `CLAUDE.md`, or `@`-include
this file. Language-agnostic; the deterministic half is enforced by the gate.

## One function, one thing

A function does **one thing** when it works at a single level of abstraction and
has **one reason to change** (SRP). Practical tests:

- **Name it honestly.** If the truthful name needs an "and" (`validateAndSave`,
  `fetchThenFormat`), it's two functions wearing one name. Split until each name
  is a single verb phrase.
- **Decide *or* do, not both.** Separate the code that *chooses* (policy, branching)
  from the code that *performs* each choice (mechanism). A method that both selects
  a strategy and executes it is doing two things.
- **One screen.** If you scroll to hold it in your head, it's carrying too much.
- **Cohesive parameters.** A long parameter list means the function juggles too
  many concerns — introduce a parameter object or split the responsibility.

## The deterministic tripwires

The structural-smell gate enforces the **mechanical** half automatically, before
any review — these are the machine-checkable shadows of "one thing":

| Smell | What it's telling you |
|---|---|
| `oversized-function` | too long to be one thing |
| `high-complexity` (cyclomatic) | too many branches = too many things |
| `too-many-parameters` | too many collaborators for one job |
| `deep-nesting` | a nested block usually wants to be a named function |

Clearing these is **necessary, not sufficient**: a short, low-complexity function
can still do two things. The mechanical checks buy you the floor; the judgment —
"is this *one* thing?" — is yours and the reviewer's.

## Reduce length and complexity for real — via the right seam

Length and cyclomatic complexity are **real problems, not just numbers to satisfy**:
a long, branchy function is hard to read and change no matter what. So genuinely
reduce them — but by finding the **right seam**, not by shattering a coherent
function into anemic one-liners to dodge a threshold (that scatters one thing across
many and reads worse). Each extracted piece should *name* one thing; usually that's
a humble well-named helper, sometimes a value object or a strategy — the **name**
matters, not the grandeur, and you don't need a domain concept to justify extracting
a step. Litmus test: if the helper you're extracting needs five parameters, the seam
is wrong — the concern didn't actually separate.

## Why it's a Foundry standard

Deep, single-purpose functions are what keep a codebase navigable to the next
reader — human or agent. It's the same thesis as the gate itself: the cheapest bug
is the one the structure made hard to write. (See also the `codebase-design`
skill's "deep modules" vocabulary — a deep module is this principle at the module
scale.)
