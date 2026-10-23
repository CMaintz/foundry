import assert from 'node:assert/strict';
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { test } from 'node:test';

// The invariant (spec foundry-jev-integration, deterministic oracle / probabilistic
// proposer): the gate may test Jev code, never call Jev for a verdict. A GATE-defining
// file - a gate workflow or a mise verb - that runs a Jev script would put a
// ~68%-accurate model in the authoritative pass/fail path. This test reds the build if
// that happens.
//
// Running Jev's own unit tests is not a verdict, so `node --test` over paths that all end
// in `.test.mjs` is exempt. The exemption is stripped token by token and only from the
// front of the argument list, so `node --test scripts/jev/review.mjs` (or a test path
// followed by a real script) still reds. Run from the repo root.
//
// Leash (@cmaintz/leash) is the same kind of advisory Jev consumer, so its Jev-calling
// subcommands are banned too. Its deterministic ones (guard, compile, report) stay
// allowed: `leash guard` is a plain rubric diff and is meant to run in CI.
const LEASH_JEV = /(?:\bleash|@cmaintz\/leash)\s+(?:check|audit|edit-check|edit-hook|hook|calibrate|bench)\b/;
const JEV_TEST_RUN = /\bnode\s+--test(?:\s+[^\s"'`;&|)]+\.test\.mjs(?=$|[\s"'`;&|)]))+/g;
const BANNED = [
  { label: 'scripts/jev', matches: (text) => text.replace(JEV_TEST_RUN, '').includes('scripts/jev') },
  { label: 'a Jev-calling leash command', matches: (text) => LEASH_JEV.test(text) },
];

const GATE_WORKFLOWS = [
  'gate.yml',
  'security.yml',
  'tier0.yml',
  '_ts.yml',
  '_java.yml',
  '_dotnet.yml',
  '_php.yml',
  '_guards.yml',
  '_semgrep.yml',
].map((name) => join('.github/workflows', name));

function miseFiles() {
  let templates = [];
  try {
    templates = readdirSync('mise')
      .filter((name) => name.endsWith('.toml'))
      .map((name) => join('mise', name));
  } catch {}
  return ['mise.toml', ...templates];
}

function bannedReference(text) {
  return BANNED.find(({ matches }) => matches(text))?.label;
}

function assertNoneReference(files, why) {
  for (const file of files) {
    if (!existsSync(file)) continue;
    const label = bannedReference(readFileSync(file, 'utf8'));
    assert.ok(!label, `${file} references ${label} - ${why}`);
  }
}

test('no gate workflow references the jev scripts', () => {
  assertNoneReference(GATE_WORKFLOWS, 'Jev must stay out of the CI gate');
});

test('no mise gate verb references the jev scripts', () => {
  assertNoneReference(miseFiles(), 'Jev must stay off the deterministic gate');
});

test('the guard bans calling a Jev script and allows running its tests', () => {
  for (const banned of [
    'node scripts/jev/review.mjs origin/main',
    'node scripts/jev/precheck.mjs satisfies "criteria"',
    'node --test scripts/jev/review.mjs',
    'node --test scripts/jev/review.mjs scripts/jev/route.test.mjs',
    'node --test scripts/jev/route.test.mjs && node scripts/jev/review.mjs',
  ]) assert.equal(bannedReference(banned), 'scripts/jev', banned);
  for (const allowed of [
    'node --test scripts/jev/*.test.mjs',
    'run = "node --test scripts/jev/*.test.mjs"',
    'node --test scripts/jev/route.test.mjs scripts/jev/client.test.mjs',
  ]) assert.equal(bannedReference(allowed), undefined, allowed);
});

test('the root mise.toml is scanned with the mise templates', () => {
  assert.ok(miseFiles().includes('mise.toml'));
});

test('the leash pattern bans Jev-calling commands and allows the deterministic ones', () => {
  for (const cmd of ['leash check --turn', 'npx @cmaintz/leash audit', 'leash bench']) assert.ok(LEASH_JEV.test(cmd), cmd);
  for (const cmd of ['leash guard origin/main', 'leash compile', 'leash report', 'leash-hook.sh']) assert.ok(!LEASH_JEV.test(cmd), cmd);
});
