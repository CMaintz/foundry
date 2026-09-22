# dependency-cycle — two or more modules import each other

**What it's telling you.** Module A imports B, and B (directly or through a chain) imports
back to A. A cycle means the modules are really one tangled unit: you can't understand,
test, build, or reuse either without the other, and the "boundary" between them is
fiction. Cycles are where refactors go to die.

**Fix toward breaking the loop, not hiding it.**
- **Find the edge that points the wrong way.** Usually one import in the cycle violates
  the intended direction. Reverse it by depending on an abstraction: extract the shared
  contract (an interface/type) into a module both can depend on, so the concrete
  dependency points one way only.
- **Extract the shared piece.** If A and B both need X, X wants to be its own module that
  both import — not something one owns and lends to the other.
- **Split a module that wears two hats.** A cycle often means a module has two
  responsibilities, one of which belongs on the other side of the boundary. Move it.

**Don't game it.**
- Making the import dynamic/lazy (a deferred `require`, a runtime lookup, a string path)
  so the static detector stops seeing the edge does **not** break the cycle — the runtime
  coupling is still there, now invisible. This is strictly worse.
- Deleting the no-circular rule or freezing the cycle into the baseline for *new* code
  hides a structural defect. Baselining is only for pre-existing debt you'll pay down.
- Merging A and B into one file to "remove" the cross-module edge trades a visible cycle
  for a bigger blob — the smell moves, it doesn't leave.

The rule is a proxy for "modules have a direction and can stand alone." Break the loop by
introducing the missing abstraction; that's the change that makes the graph reasoning-
friendly again.
