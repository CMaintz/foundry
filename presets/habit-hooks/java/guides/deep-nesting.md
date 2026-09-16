A block nested this deep (3+) forces the reader to hold several unstated conditions at once. The depth is the symptom; a method doing too much in one place is the cause.

**Flatten it, one level at a time:**
1. Invert and return early: `if (ok) { ...big... }` → `if (!ok) return; ...big...`. Preconditions become guards and the pyramid collapses.
2. Extract the inner block into a private method named for its precondition — the nesting moves behind a call that documents *when* it runs.
3. Combine conditions that are really one rule: `if (a) if (b) if (c)` → `if (a && b && c)` (name it if non-obvious).
4. In loops, pull the body into a method taking one element, and `continue` on the skip case instead of wrapping the body in an `if`.

Useful tip: every level of indentation should earn its place — if you can't say what condition it represents, it wants to be flattened or named.

**AVOID:** moving the whole pyramid into a helper unchanged — extract the *inner* concern, don't just relocate the nesting.

You are done when no block is more than two levels deep and the happy path reads straight down.

{% include "includes/line_level_issues.md" %}
