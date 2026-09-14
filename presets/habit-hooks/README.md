# habit-hooks presets

## Config is shareable; the baseline is not

Two files make up a repo's habit-hooks setup, and only one of them can be universal:

- **`config.toml`** — *which* smells run (plugins + file globs). This is a
  convention and **can** be shared. Copy a preset from here.
- **`snooze.json`** — the *accepted existing violations* of one specific repo. It
  lists real files and counts, so it is inherently **per-repo** and cannot be a
  shared baseline. Generate it once per repo with `habit-sensors --all | habit-snooze --snooze`.

So "a universal baseline" = a universal **config**, not a universal snooze list.

## The universal part

The `generic` plugin (jscpd duplication detection) is language-independent and
belongs in every repo. Every preset below includes it. That is the closest thing
to a truly universal check.

## Presets

| File | Plugins | For |
|---|---|---|
| `typescript.toml` | typescript, generic | TS/JS (eslint, knip, ts-morph) |
| `java.toml` | java, generic | Java (PMD → oversized-file/function, etc.) |
| `php.toml` | php, generic | PHP (phpmd) |
| `kotlin.toml` | generic | Kotlin — smells via detekt in `mise run lint` (no habit-hooks sensor yet) |
| `dotnet.toml` | generic | .NET/C# — smells via Roslyn analyzers in `mise run lint` |
| `python.toml` | generic | Python — smells via ruff in `mise run lint` |

For languages with no habit-hooks sensor of their own (Kotlin, .NET, Python), the
preset runs only the language-independent `generic` (jscpd) duplication check; the
language's own linter carries the structural smells inside the `lint` verb.

Copy one to `<repo>/.habit-hooks/config.toml`, install the detectors
(`habit-hooks init` lists them), then snooze the baseline.

Thresholds (oversized-file at 200 lines, etc.) use habit-hooks' own defaults —
the same numbers everywhere, which is exactly the point: file-length limits apply
to Java and PHP just as they do to TypeScript.

HTML/CSS have no habit-hooks plugin; use foundry's reusable `web.yml` workflow for
a max-file-length gate on those.

## Tests are not smell-scanned (every preset)

Every preset does this as **a positive include followed by a `!` exclusion**, e.g.
`files = ["**/*.java", "!**/src/test/**/*.java"]`. ⚠️ **A bare exclusion
(`files = ["!…"]`) matches *nothing* and silently disables the entire scan** —
`habit-sensors` needs at least one positive glob, or it reports "nothing matched
[files]" (and `--snooze` will happily write an empty baseline, hiding it). Always
lead with the include. This is a **language-agnostic principle**, not a per-language
quirk: long, mock-heavy test methods and piles of fixtures are *normal and correct*
in tests. Structural-smell gates exist
to police **production** maintainability; pointing them at tests just generates
noise you'll snooze anyway. The glob differs per language (`**/src/test/**` for
Java, `*.spec.ts`/`*.test.ts` for TS, `**/tests/**`/`*Test.php` for PHP) but the
rule is the same everywhere. If a test is *genuinely* unreadable, that's a separate
readability task — not something CI should block a feature PR on.

## Tuning thresholds — project ruleset over config edits

Two ways to change what fires, in order of preference:

1. **Disable or retune a smell in `config.toml`** — `[smells.<name>] disabled = true`,
   or pass detector args under `[sensors.<name>] args = [...]`. ⚠️ **`args` must be a
   TOML array, never a string** — habit-hooks mangles a string into per-character
   tokens (PMD then reports "Cannot load ruleset -/n/o/…" and the scan breaks). `java.toml`
   ships two worked examples: silencing PMD's progress bar, and disabling `unused-import`
   (PMD runs without a classpath here, so it false-flags wildcard imports — and a
   formatter already enforces unused-imports correctly in the gate).
2. **Drop a project ruleset** — for Java, a `pmd/ruleset.xml` in the repo is
   preferred by the sensor over its bundled ruleset, and findings still map to
   smells **by PMD rule name**. Copy `../pmd/ruleset.xml`: it's the bundled ruleset
   with `ExcessiveParameterList minimum` raised 4 → 8, so `too-many-parameters`
   stops firing on ordinary DI constructors/records and only flags a real god-class.

Either way, **retuning is a deliberate, reviewable change** — foundry's
`ruleset-guard` treats config/ruleset files as gate-defining and blocks a source PR
that loosens them without a `ruleset-change` label.

> **TOML gotcha:** top-level keys (`plugins`, `files`) must appear *before* any
> `[table]` header, or the parser attributes them to the table and your globs
> silently vanish.
