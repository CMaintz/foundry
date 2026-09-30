import assert from 'node:assert/strict';
import { existsSync, readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { test } from 'node:test';

// The invariant (spec foundry-jev-integration, deterministic oracle / probabilistic
// proposer): Jev is advisory-only and must NEVER be referenced by a GATE-defining file -
// a gate workflow or a mise verb. A reference there would put a ~68%-accurate model in
// the authoritative pass/fail path. This test reds the build if that happens.
//
// It scans the gate files explicitly (not every workflow) so a separate test-runner
// workflow that runs these very tests is allowed - that is not the gate. Run from the repo root.
const BANNED = 'scripts/jev';

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
  try {
    return readdirSync('mise')
      .filter((name) => name.endsWith('.toml'))
      .map((name) => join('mise', name));
  } catch {
    return [];
  }
}

function assertNoneReference(files, why) {
  for (const file of files) {
    if (!existsSync(file)) continue;
    assert.ok(!readFileSync(file, 'utf8').includes(BANNED), `${file} references ${BANNED} - ${why}`);
  }
}

test('no gate workflow references the jev scripts', () => {
  assertNoneReference(GATE_WORKFLOWS, 'Jev must stay out of the CI gate');
});

test('no mise gate verb references the jev scripts', () => {
  assertNoneReference(miseFiles(), 'Jev must stay off the deterministic gate');
});
