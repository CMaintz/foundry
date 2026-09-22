// Foundry architecture fitness — TypeScript (dependency-cruiser).
//
// Deterministic, whole-graph enforcement of YOUR architecture: forbids cross-layer
// imports and dependency cycles. Runs under `lint` (fold in when your layer map is
// filled — see mise/ts.toml `arch` task). It is whole-program, so it always runs
// whole-tree, never changed-scoped (a cycle can be formed by an unrelated edge).
//
// ARCHITECTURE-AGNOSTIC. You describe *your* layers once, in LAYERS + ALLOW; every
// rule is generated from that. Hexagonal is only the default example — swap in any of
// the maps at the bottom (classic-layered, clean/onion, modular) or write your own.
//
//   A "layer" is a set of source paths (regex, matched against the module path).
//   ALLOW[x] lists the layers x MAY import; any layer not listed is forbidden.
//   Cycles are always forbidden. Framework-freedom is a FORBIDDEN_IMPORTS rule.
//
// Ratchet: generate today's violations as a baseline that may only shrink, and fail
// only on NEW ones (see the `options` note). ruleset-guard watches the baseline.

/** layer name -> path regex (matched against the resolved module path). */
const LAYERS = {
  domain: "^src/domain/",
  usecase: "^src/(usecase|application)/",
  adapter: "^src/adapter/",
  infra: "^src/(infra|config)/",
};

/** allowed *internal* dependencies per layer; omit or [] => may import nothing internal. */
const ALLOW = {
  domain: [], // framework-free core: depends on no other layer
  usecase: ["domain"],
  adapter: ["usecase", "domain"],
  infra: ["adapter", "usecase", "domain"],
};

/** layers that must not import a given third-party package regex (framework-freedom). */
const FORBIDDEN_IMPORTS = [
  // { layers: ["domain"], packages: "^(@angular|@nestjs|express|typeorm)" },
];

// ---------------------------------------------------------------------------
// Generation — you should not need to edit below this line.
// ---------------------------------------------------------------------------
const names = Object.keys(LAYERS);

const layerRules = names
  .map((name) => {
    const allowed = new Set([name, ...(ALLOW[name] || [])]);
    const forbidden = names.filter((n) => !allowed.has(n));
    if (forbidden.length === 0) return null;
    return {
      name: `layer-${name}`,
      comment: `${name} may import only {${[...allowed].join(", ")}} (+ externals). See presets/arch/guides/layering-violation.md`,
      severity: "error",
      from: { path: LAYERS[name] },
      to: { path: forbidden.map((n) => LAYERS[n]) },
    };
  })
  .filter(Boolean);

const frameworkRules = FORBIDDEN_IMPORTS.map((r, i) => ({
  name: `no-framework-in-${r.layers.join("-")}-${i}`,
  comment: `${r.layers.join("/")} must stay framework-free. See presets/arch/guides/layering-violation.md`,
  severity: "error",
  from: { path: r.layers.map((l) => LAYERS[l]) },
  to: { path: r.packages, dependencyTypes: ["npm", "npm-dev", "npm-peer"] },
}));

module.exports = {
  forbidden: [
    {
      name: "no-circular",
      comment: "Dependency cycles make the module graph impossible to reason about or test in isolation. See presets/arch/guides/dependency-cycle.md",
      severity: "error",
      from: {},
      to: { circular: true },
    },
    ...layerRules,
    ...frameworkRules,
  ],
  options: {
    doNotFollow: { path: "node_modules" },
    tsConfig: { fileName: "tsconfig.json" },
    // Ratchet (verify exact flags for your dependency-cruiser version): generate a
    // known-violations baseline once, commit it, and run against it so only NEW
    // violations fail. The baseline may only shrink; ruleset-guard watches it with
    // the `snooze` kind (value_counts over the JSON). Example:
    //   depcruise src --config presets/arch/dependency-cruiser.cjs \
    //     --output-type baseline > .dependency-cruiser-known-violations.json
    //   depcruise src --config presets/arch/dependency-cruiser.cjs \
    //     --ignore-known .dependency-cruiser-known-violations.json
  },
};

// ---- example maps for other architectures (replace LAYERS + ALLOW above) ----
//
// Classic layered (n-tier):
//   LAYERS = { web: "^src/(controller|web)/", service: "^src/service/", data: "^src/(repo|dao)/" }
//   ALLOW  = { web: ["service"], service: ["data"], data: [] }
//
// Clean / onion:
//   LAYERS = { entities:"^src/entities/", usecases:"^src/usecases/", ifaces:"^src/interfaces/", fw:"^src/frameworks/" }
//   ALLOW  = { entities:[], usecases:["entities"], ifaces:["usecases","entities"], fw:["ifaces","usecases","entities"] }
//
// Modular / feature-sliced (feature isolation — features never import each other,
// only a shared kernel): give each feature its own layer whose ALLOW is ["shared"]:
//   LAYERS = { shared:"^src/shared/", billing:"^src/features/billing/", auth:"^src/features/auth/" }
//   ALLOW  = { shared: [], billing: ["shared"], auth: ["shared"] }   // billing !-> auth, auth !-> billing
