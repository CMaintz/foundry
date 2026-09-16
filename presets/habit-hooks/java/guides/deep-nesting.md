**deep-nesting** — a block nested this deep (3+) is hard to follow: each level is an unstated condition the reader must hold in their head.

Flatten it — a deeply nested block almost always wants to be a named method or an earlier exit:
- **Invert and return early.** `if (ok) { ...big... }` → `if (!ok) return; ...big...`. Collapse the pyramid one level at a time.
- **Extract the inner block** into a private method with a name that states its precondition — the nesting moves behind a call, and the name documents *when* it runs.
- **Replace nested `if`s with a combined guard** where the conditions are really one rule: `if (a) if (b) if (c)` → `if (a && b && c)` (then name it if it's non-obvious).
- **Loops:** pull the loop body into a method taking one element; `continue` on the skip case instead of wrapping the body in an `if`.

**Don't** keep the depth and just move the whole pyramid into a helper — extract the *inner* concern so each level earns its place.
