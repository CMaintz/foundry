**oversized-function** — this method is long enough that it's holding more than one idea.

Length is a symptom, not the disease: the fix is to find the *seam*, not to hit a line count.
- Read the body for **paragraphs** — groups of statements separated by blank lines or a comment. Each is usually one step that wants its own well-named private method.
- Separate **deciding from doing**: if the method both chooses *what* to do (branching on a type/flag) and does it, pull each branch's work into its own method (or a strategy) and leave the method as the chooser.
- Extract toward a **name**, not a number. `enrichAndPersistAndNotify(...)` → `enrich(...)`, `persist(...)`, `notify(...)`. If the honest name of an extracted piece needs an "and", split again.

**Don't** just cut the body at the halfway line into `fooPart2(...)`, and **don't** extract a helper that needs 5+ parameters — that means the seam is wrong and you've smeared one thing across two methods. Refactor toward cohesion; the smell clears as a side effect.
