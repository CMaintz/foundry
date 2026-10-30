// The Jev provider port for Foundry's advisory layer. Re-exports the published
// @cmaintz/jev-core client (https://github.com/CMaintz/jev-tools), vendored under
// ./vendor/jev-core so these scripts run with plain node and no install. Update it with
// `scripts/jev/vendor-jev-core.sh <version>`; never edit the vendored files by hand.
//
// ADVISORY ONLY. Nothing here may run in a gate verb (lint/typecheck/test/audit) or a
// gate workflow; boundary.test.mjs fails the build if it does.
// Jev routes where to spend expensive LLM effort; it never decides pass/fail.
//
// Needs Node 20.3+ (global fetch, AbortSignal.any).

export { CloudflareProvider, TypeSafeProvider, postJson, providerFromEnv } from './vendor/jev-core/index.js';
