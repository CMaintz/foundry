A long parameter list is coupling: parameters that travel together are a missing abstraction, and on a constructor it usually means the class does too much (threshold is 8).

**Find the missing abstraction:**
1. Look at the call sites — does a group of these parameters already belong to an existing type? Values that keep appearing side by side are usually one of the domain's own nouns; where that name exists, it's the answer.
2. If not, make a small `record` for the group (e.g. `DocumentRequest`, `GenerationOptions`) and move behaviour that uses those fields onto it.
3. On a constructor with 8+ injected dependencies, that's a god class: extract a collaborator (a sub-service, an assembler) that owns a cohesive slice and inject that instead.
4. Drop anything derivable from another parameter.

Useful tip: rewrite a call site with the signature that feels natural there, and let that shape the type.

**AVOID:** a `Map<String,Object>` or `Object...` bag, or a `FooParams` object named after the method rather than a real concept — that renames the list instead of removing the coupling, so the next method invents another one.

You are done when the parameters carry a domain name and no call site still passes their fields loose.

{% include "includes/line_level_issues.md" %}
