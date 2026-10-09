# Adopting architecture fitness

A quick-guide for humans and agents turning on Foundry's architecture checks. These are
deterministic, whole-graph structural rules — "the domain stays framework-free",
"adapters never leak into the core", "no dependency cycles" — the kind of thing a
documented architecture loses one "just this once" import at a time. They are **pure
oracle**: no model, no flakiness, same answer locally and in CI.

The mechanism is the same on every stack:

1. **You declare your architecture** as a small layer map — which packages are which
   layer, and which layers each may import. Anything not allowed is forbidden. This is
   *your* architecture, not a preset; hexagonal is only the default example.
2. **A deterministic tool enforces it** by walking the whole module graph — dependency-
   cruiser (TS), ArchUnit (Java), import-linter (Python).
3. **A shrink-only baseline** freezes today's violations so you can retrofit onto a dirty
   codebase without a red day-one wall. New violations fail; the baseline may only ever
   shrink. `ruleset-guard` enforces that in CI.
4. **It runs inside an existing verb** — `test` on Java, `lint` on TS/Python — so callers
   never learn a new command. The arch check hides behind the verb interface exactly as
   CONTRACT.md intends.

It is opt-in per repo. Until you fill the layer map, `mise run arch` exits 0, and nothing
runs it. Adoption = fill the map, freeze the baseline, then fold `arch` into the verb.

> **The one rule that matters:** never widen the architecture to make a build pass.
> Deleting a rule, widening what a layer may import, or growing the baseline is a
> deliberate decision that gets its own PR with the `ruleset-change` label. CI blocks it
> otherwise. Tightening (removing a violation, pruning the baseline) is always free —
> except on Python, see that section.

---

## TypeScript — dependency-cruiser (runs under `lint`)

**Preset:** `presets/arch/dependency-cruiser.cjs` · **Baseline:**
`.dependency-cruiser-known-violations.json` (separate file) · **Verb:** `lint`

1. `npm i -D dependency-cruiser` (pin the version).
2. Copy the preset to the repo root as `.dependency-cruiser.cjs` and fill the two maps at
   the top — `LAYERS` (layer name → path regex) and `ALLOW` (per layer, which layers it
   may import). Four worked maps ship in the file (hexagonal, classic-layered,
   clean/onion, modular); swap one in or write your own. `FORBIDDEN_IMPORTS` adds
   framework-freedom (e.g. domain must not import `@nestjs`).
3. Freeze today's violations:
   ```
   depcruise src --config .dependency-cruiser.cjs \
     --output-type baseline > .dependency-cruiser-known-violations.json
   ```
   Commit that file. Then the enforcing run is `depcruise src --config
   .dependency-cruiser.cjs --ignore-known .dependency-cruiser-known-violations.json` —
   which is exactly what `mise run arch` runs once the config exists.
4. **Fold into `lint`.** The `arch` task in `mise/ts.toml` is tier-c auxiliary. Once your
   map is filled, add `mise run arch` to the `lint` task so it gates for real.
5. `ruleset-guard` watches the baseline JSON with the `snooze` kind — an added violation
   fails the guard; pruning passes label-free.

---

## Java — ArchUnit (runs under `test`)

**Preset:** `presets/arch/ArchitectureTest.java` · **Baseline:** `archunit_store/`
(committed directory) · **Verb:** `test` (ArchUnit rules *are* JUnit tests)

This is the deepest of the three because the freeze mechanism has moving parts. Follow it
in order.

1. **Add the dependency** (pin the version):
   - Gradle (KTS): `testImplementation("com.tngtech.archunit:archunit-junit5:1.3.0")`
   - Maven: `<dependency><groupId>com.tngtech.archunit</groupId><artifactId>archunit-junit5</artifactId><version>1.3.0</version><scope>test</scope></dependency>`
2. **Drop in the test.** Copy `ArchitectureTest.java` to `src/test/java/<your-base>/arch/`.
   Change two things: the `package` declaration, and the `packages = "com.example"` base
   package in `@AnalyzeClasses` (plus the `slices().matching("com.example.(*)..")` line).
   Edit the layer rules to your architecture — the file ships hexagonal as default with
   classic-layered / clean-onion / modular examples at the bottom. Every rule is already
   wrapped in `FreezingArchRule.freeze(...)`.
3. **Configure the freeze store.** Create `src/test/resources/archunit.properties`:
   ```properties
   freeze.store.default.path=archunit_store
   freeze.store.default.allowStoreCreation=true
   ```
   `allowStoreCreation` defaults to **false**, so without it the very first run fails
   instead of recording the baseline. Leave it `true` so a fresh checkout / new rule can
   seed its store.
4. **First run seeds the store.** Run `mise run test` once. ArchUnit records today's
   violations into `archunit_store/` and the test passes. **Commit that directory.**
   Thereafter only *new* violations fail, and the store may only shrink.
5. **Normalize line endings.** Add to `.gitattributes`:
   ```
   archunit_store/** text eol=lf
   ```
   (Foundry's root `.gitattributes` already forces `* text=auto eol=lf`; adopters who
   vendor it are covered, but set it explicitly if yours doesn't — otherwise Windows
   contributors get a phantom whole-file diff.)
6. **Never refreeze to pass.** `freeze.refreeze=true` regenerates the whole store from
   current reality — it is the "accept everything" escape hatch. Setting it, or deleting
   the store, is a `ruleset-change` PR, never a fix. `ruleset-guard` watches the store
   files with the `lines` kind (one frozen violation per line), so an added line fails the
   guard.
7. **Keep arch tests off changed-scope selection.** They are cheap and global; a
   changed-scope `test` run must never skip them, or a cross-layer import in an "untouched"
   file sails through. Put them in a package/source set your test selection always
   includes.

In-loop placement is TS/Python only — ArchUnit needs a compiled classpath, which is too
slow for the Stop hook. Java arch runs at pre-push and CI (see the design doc §7.4).

---

## Python — import-linter (runs under `lint`)

**Preset:** `presets/arch/importlinter.ini` · **Baseline:** inline `ignore_imports` lines
(same file) · **Verb:** `lint` (via the `arch` task) · **Pinned:** `import-linter` in the
project `.venv` (`mise/python.toml` already wires it)

1. Copy `presets/arch/importlinter.ini` to `.importlinter` at the repo root (or inline it
   under `[tool.importlinter]` in `pyproject.toml`).
2. Set `root_package` to your top package, and fill the `layers` contract. **Mental-model
   shift from TS:** a layer is a *module path under `root_package`*, not a filesystem
   regex, and layers are listed **high → low** (a higher layer may import a lower one, not
   the reverse). Independent siblings go on one line separated by ` | `. The preset ships
   hexagonal plus classic-layered / clean-onion / modular (`independence` contract)
   examples.
3. Framework-freedom uses a `forbidden` contract and needs `include_external_packages =
   True` at the top (already set in the preset). It names the frameworks your core must
   not import.
4. **Freeze today's violations as `ignore_imports`** — one `importer -> imported` line per
   accepted violation, inside the contract. This is the baseline; it may only shrink.
5. **Fold into `lint`.** Add `mise run arch` to the `lint` task in `mise/python.toml` once
   your contracts are filled. `lint-imports` runs from the project `.venv`.

**Two honest differences from TS/Java — read these:**

- **No whole-graph cycle check.** The `layers` contract enforces one-way direction between
  the named layers (which rules out cross-layer cycles), but import-linter has no
  equivalent of dependency-cruiser's "no cycles anywhere". If you need that, it is not
  covered here.
- **Pruning the baseline needs a `ruleset-change` label.** import-linter keeps
  `ignore_imports` *inline* in the ruleset file — there is no separate baseline file to
  prune label-free. So any edit to `.importlinter` beside production source trips the
  ruleset-change control, including *removing* an ignore. The rot-prevention half still
  works for free: `unmatched_ignore_imports_alerting = error` (the default) fails the
  build when an `ignore_imports` entry no longer matches a real import, so a fixed
  violation can't sit silently suppressed.

Python's `.importlinter` preset is new — if your repo predates it, pull latest before
adopting.

---

## For agents

Exact, non-interactive steps. The arch check is deterministic — a green `gate` with arch
folded in is authoritative; your own reasoning about layering is not.

**Detect adoption state:** `mise run arch` exits 0 with a "no config yet" line when
unadopted. Present config means it gates.

| Stack | Enforcing command | Baseline artifact | ruleset-guard kind |
|---|---|---|---|
| TS | `depcruise src --config .dependency-cruiser.cjs --ignore-known .dependency-cruiser-known-violations.json` | `.dependency-cruiser-known-violations.json` | `snooze` |
| Java | `mise run test` (ArchUnit via JUnit) | `archunit_store/` | `lines` |
| Python | `lint-imports` | inline `ignore_imports` in `.importlinter` | — (ruleset-file watch) |

**Safe without a `ruleset-change` label** (tightening): removing a violation from the
code; pruning the TS baseline JSON or a Java store line. **Requires the label**
(loosening): widening `ALLOW`/`layers`, deleting a rule, adding a baseline entry, Java
`freeze.refreeze=true`, and — Python only — *any* edit to `.importlinter` including
pruning an `ignore_imports` line.

**Never** regenerate a baseline wholesale (`--output-type baseline` over existing,
`freeze.refreeze=true`, rewriting `ignore_imports`) to make a build pass. That erases the
ratchet. Fix the import, or open a labelled PR.

**Acceptance checks after wiring** (from the design doc): a new cross-layer import fails
the verb with a coaching guide; an existing violation in the baseline does not fail;
removing a violation + pruning passes `ruleset-guard` (TS/Java label-free; Python with the
label); a new package cycle fails (TS/Java).

See `docs/designs/arch-fitness.md` for the full design and `presets/arch/guides/` for the
failure-time coaching guides.
