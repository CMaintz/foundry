import assert from 'node:assert/strict';
import { readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { test } from 'node:test';

// The invariant (spec foundry-jev-integration, deterministic oracle / probabilistic
// proposer): Jev is advisory-only and must NEVER be referenced by a gate-defining
// file - not a CI workflow, not a mise gate verb. A reference here would mean a
// ~68%-accurate model crept into the authoritative pass/fail path. This test makes
// that a red build rather than a code-review hope. Run from the repo root.
const BANNED = 'scripts/jev';

function filesIn(dir, ext) {
  try {
    return readdirSync(dir)
      .filter((name) => name.endsWith(ext))
      .map((name) => join(dir, name));
  } catch {
    return [];
  }
}

function assertNoneReference(files, why) {
  for (const file of files) {
    assert.ok(!readFileSync(file, 'utf8').includes(BANNED), `${file} references ${BANNED} - ${why}`);
  }
}

test('no CI workflow references the jev scripts', () => {
  assertNoneReference(filesIn('.github/workflows', '.yml'), 'Jev must stay out of CI');
});

test('no mise gate verb references the jev scripts', () => {
  assertNoneReference(filesIn('mise', '.toml'), 'Jev must stay off the deterministic gate');
});
