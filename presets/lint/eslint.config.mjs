// Foundry base ESLint config (flat, ESLint 9+). Deliberately minimal and
// framework-agnostic: a *default* to extend, not a full ruleset. Vendor it (e.g.
// `eslint.config.foundry.mjs`) and spread it into your project's config:
//
//   import foundry from "./eslint.config.foundry.mjs";
//   export default [ ...foundry, /* your framework + project rules */ ];
//
// What it owns: **line length as a gate** - the one thing habit-hooks' TS sensor
// doesn't cover (that sensor already handles loose-equality, non-const-binding,
// explicit-any, dead code, etc., so this doesn't duplicate them).
//
// max-len is 120, but strings / template literals / regex / URLs are exempted so a
// prompt or a long formatted line doesn't trip it - extract a big prompt to its own
// module rather than fight the linter. NB max-len is not auto-fixable: **Prettier's
// `printWidth` is what actually wraps code** - if you run Prettier, set printWidth 120
// so wrapping is automatic and max-len is only the hard backstop for what it can't wrap.
//
// Unused disable directives are errors: a disable whose violation is gone would otherwise
// sit there and silently cover the next violation on that line. Inline config stays
// allowed (no `noInlineConfig`); the CI ruleset-guard makes every added disable or inline
// rule config a labelled decision instead.
export default [
  {
    linterOptions: {
      reportUnusedDisableDirectives: "error",
    },
    rules: {
      "max-len": [
        "error",
        {
          code: 120,
          tabWidth: 2,
          ignoreStrings: true,
          ignoreTemplateLiterals: true,
          ignoreRegExpLiterals: true,
          ignoreUrls: true,
          ignoreComments: false,
        },
      ],
    },
  },
];
