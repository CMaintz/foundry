An oversized method is holding more than one idea. Length is the symptom; a method doing several jobs is the cause.

**Find the seam and extract toward a name:**
1. Read the body in paragraphs — statements grouped by a blank line or a comment. Each is usually one step that wants its own well-named private method.
2. Separate deciding from doing: if the method both *chooses* what to do (a switch on a type/flag) and does it, move each branch's work into its own method or a strategy, and leave this method as the chooser.
3. Name each piece for the responsibility it owns. `enrichAndPersist(...)` is two methods: `enrich(...)` then `persist(...)`.

Useful tip: describe the method in one honest sentence. If the sentence needs an "and", each half is a method.

**AVOID:** cutting the body at the halfway line into `fooPart2(...)`, or extracting a helper that takes 5+ parameters — that smears one idea across two methods (the seam is wrong). The count moves; the tangle stays.

You are done when the method reads as a short list of well-named steps and a first-time reader can hold it in their head.

{% include "includes/line_level_issues.md" %}
