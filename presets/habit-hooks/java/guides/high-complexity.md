High complexity means one method makes too many decisions at once. The count (every `if`/`else`/`case`/`&&`/`||`/loop/`?:`) is the symptom; tangled responsibilities are the cause.

**Remove decisions, don't hide them:**
1. Lift guards out first — turn precondition checks into early returns so the happy path stays flat. Much of the count is preconditions wrapped around the real work.
2. Change the shape of what remains: a `switch`/`if`-chain on one value is often polymorphism in disguise (a sealed interface + implementations, an enum with an abstract method) or a `Map` lookup; a nested loop is often a filter/map pipeline.
3. If the branches are genuinely separate jobs, extract one method per branch, each named for what it handles.

Useful tip: describe each branch in one sentence. Two branches with the same sentence belong together; a branch you can't name cleanly wants its own method.

**AVOID:** merging conditions with `&&`/`||`, or rewriting branches as ternaries, just to lower the score — the decisions remain, only the counter moves.

You are done when a first-time reader can follow the method top to bottom without backtracking.

{% include "includes/line_level_issues.md" %}
