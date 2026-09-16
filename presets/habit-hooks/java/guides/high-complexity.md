**high-complexity** — too many branches/paths in one method: too many decisions living in one place.

Cyclomatic complexity counts the independent paths (every `if`/`else`/`case`/`&&`/`||`/loop/`?:`). Bring it down by removing decisions, not by hiding them:
- **Guard clauses / early return.** Handle the invalid or edge cases up front and `return`, so the happy path drops an indentation level and the trailing `else` blocks disappear.
- **Replace type/enum switches with polymorphism.** A `switch` on a kind that recurs across the class is a missing type — push each case's behaviour onto the type (a sealed interface + implementations, a strategy, an enum with an abstract method).
- **Lift boolean tangles into named predicates.** `if (a && (b || c) && !d)` → `if (isEligible(...))` with the condition named once.
- **Table/map over branches.** A long `switch` that just maps input → value is a `Map` lookup.

**Don't** split the method purely to move complexity into a helper that's just as branchy — that relocates the problem. Remove the decision or give it a home.
