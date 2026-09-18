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

## Refactor toward cohesion — length and complexity are the signals

The goal is **cohesion**: each function does one thing at one level of abstraction.
Length and cyclomatic complexity are the **honest signals** that it doesn't — a long,
branchy function is usually several things wearing one name — but they are signals,
not the target. Don't chase the number: mechanically shortening a function can chop
cohesion (or functionality) as easily as improve it.

Don't over-correct, either. A straight-line sequence of steps at one level is fine as
one function — **not** every step wants to be a helper. Extract where there's *real*
complexity (tangled branches) or a **pyramid of doom** (deep nesting), not to hit a
count. When you do, aim at the right seam: the missing abstraction (a value object, a
strategy, a named step in a pipeline) **or** simply a well-named helper for a coherent
step — a humble name counts, you don't need a domain concept. Litmus: a helper that
needs five parameters means the seam is wrong — the concern didn't actually separate.

## Name your values — no magic numbers or strings

A literal with meaning is a missing name. `if (status == 3)`, `retry(5)`, a repeated
`"application/json"` — give each a named constant (or an enum / config value) so the
meaning is stated once and changes in one place. The tells:

- a number or string whose meaning isn't obvious from context;
- the **same literal in two places** — they can now silently drift;
- a literal that encodes a rule (a threshold, a status code, a magic key).

Self-evident values need no name (`0`, `1`, `""`, an index step), nor does a one-off
already made clear by a well-named variable or parameter. As with length: the point is
**meaning, not a count** — don't reflexively name every `2`.

## Size limits — files and lines

- **File ≤ 300 lines** (coded files — TS/JS, Java, HTML/CSS). Over that is
  `oversized-file`, gated by habit-hooks' line-count sensor. Config, generated, data,
  and prose/prompt files are excluded by the `files` globs. Keep a large prompt or
  template in its own resource file (`.txt` / a constants file), not inline in a
  module, so the code file stays under the limit.
- **Line ≤ 100–120 chars.** Java: google-java-format (via Spotless) already wraps to
  ~100 — no separate gate — and only leaves a line long when it *can't* wrap it (an
  unbreakable string/URL), which is exactly the case you'd exempt. TS/JS: ESLint
  `max-len` (120) with `ignoreStrings` / `ignoreTemplateLiterals` / `ignoreUrls` /
  `ignoreRegExpLiterals`, so prompts and formatted text don't trip it — foundry ships
  this as [`eslint.config.mjs`](./eslint.config.mjs); extend it in your project.
  Prettier's `printWidth` (120) is what auto-wraps; `max-len` is the backstop for
  what it can't.
- **Function length / complexity count *statements and branches*, not characters** —
  a long prompt string is one statement, so it does **not** inflate `oversized-function`
  (NcssCount) or `high-complexity`. Those are about doing too much (above), never line
  width. (File length *does* count the string's lines — hence "keep big prompts in a
  resource file".)

## Why it's a Foundry standard

Deep, single-purpose functions are what keep a codebase navigable to the next
reader — human or agent. It's the same thesis as the gate itself: the cheapest bug
is the one the structure made hard to write. (See also the `codebase-design`
skill's "deep modules" vocabulary — a deep module is this principle at the module
scale.)
