**too-many-parameters** — this method/constructor takes more collaborators than one job needs (threshold is 8).

A long parameter list is a "this does too much" signal. Reduce it by grouping or by splitting the responsibility, not by packing args into an array:
- **Introduce a parameter object.** Parameters that always travel together are a concept missing a name — make a small `record` (e.g. `DocumentRequest`, `GenerationOptions`) and pass that. This often reveals validation/derivation that belongs on the record too.
- **On a constructor, it usually means the class has too many responsibilities.** 8+ injected dependencies = a god class; extract a collaborator (a sub-service, an assembler) that owns a cohesive slice of them, and inject that instead.
- **Drop what's derivable.** If one parameter can be computed from another, don't pass it.

**Don't** dodge the count with a `Map<String,Object>`, a giant `Object...` varargs, or by merging unrelated params into one bag — that hides the coupling instead of resolving it. The right parameter object names a real concept.
