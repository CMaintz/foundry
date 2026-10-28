// The structural-smell rules for TypeScript and plain JavaScript, run only by habit-hooks
// (via `[sensors.eslint] args` in .habit-hooks/config.toml). The thresholds are the ones the
// habit-hooks typescript plugin ships, so every repo is held to the same bar; that config
// can't be reused directly because the plugin only runs it for a repo with no eslint
// config, and it hard-requires typescript-eslint, which a JS repo has no reason to install.
// oversized-file is left to the generic line-count sensor, which owns the 300-line limit.
import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";

// `--config` replaces the project's eslint config for this run, so it is spread in first:
// its own rules (a security ban, say) keep reporting through habit-hooks, and its parser is
// what reads TypeScript - this file sets none, which is fine because `eslint .` in lint
// already needs the project's config to parse every .ts file. Looked up from cwd, which is
// eslint's base path under `--config` and where habit-hooks runs. Only the root config:
// `--config` also turns off eslint's per-directory lookup, so a nested package's own config
// is not seen here.
async function projectConfig() {
  const names = ["eslint.config.js", "eslint.config.mjs", "eslint.config.cjs"];
  const own = names.map((name) => path.resolve(name)).find((file) => fs.existsSync(file));
  return own ? (await import(pathToFileURL(own).href)).default : [];
}

export default [
  // flat(): a config may export one object rather than an array.
  ...[await projectConfig()].flat(),
  {
    files: ["**/*.js", "**/*.mjs", "**/*.cjs", "**/*.jsx", "**/*.ts", "**/*.tsx", "**/*.mts", "**/*.cts"],
    rules: {
      "max-lines-per-function": ["error", { max: 12, skipBlankLines: false, skipComments: false, IIFEs: true }],
      "max-params": ["error", 3],
      complexity: ["error", 10],
      "max-depth": ["error", { max: 4 }],
      eqeqeq: ["error", "always"],
      "no-var": "error",
      "prefer-const": "error",
      "no-duplicate-imports": "error",
      "no-warning-comments": ["warn", { terms: ["todo", "fixme", "xxx", "hack"], location: "anywhere" }],
    },
  },
  // JS only: the base rule reads a TS interface's parameter names as unused variables, and
  // the typescript-eslint rule needs a plugin this file cannot assume the project registered.
  {
    files: ["**/*.js", "**/*.mjs", "**/*.cjs", "**/*.jsx"],
    rules: {
      "no-unused-vars": ["error", { argsIgnorePattern: "^_", varsIgnorePattern: "^_" }],
    },
  },
];
