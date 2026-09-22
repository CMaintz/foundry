// Conventional Commits ruleset for the commitlint check (and thus the input
// release-please parses). The wagoid action bundles @commitlint/config-conventional,
// so no package.json / npm install is needed in this workflow-only repo.
export default {
  extends: ["@commitlint/config-conventional"],
};
