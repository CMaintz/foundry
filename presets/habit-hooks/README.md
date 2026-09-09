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

Copy one to `<repo>/.habit-hooks/config.toml`, install the detectors
(`habit-hooks init` lists them), then snooze the baseline.

Thresholds (oversized-file at 200 lines, etc.) use habit-hooks' own defaults —
the same numbers everywhere, which is exactly the point: file-length limits apply
to Java and PHP just as they do to TypeScript.

HTML/CSS have no habit-hooks plugin; use foundry's reusable `web.yml` workflow for
a max-file-length gate on those.
