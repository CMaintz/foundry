import assert from 'node:assert/strict';
import { test } from 'node:test';
import { parseDiff, routeFiles } from './review.mjs';

const DIFF = [
  'diff --git a/src/core/decide.ts b/src/core/decide.ts',
  'index 111..222 100644',
  '--- a/src/core/decide.ts',
  '+++ b/src/core/decide.ts',
  '@@ -1 +1 @@',
  '-old',
  '+new',
  'diff --git a/README.md b/README.md',
  '--- a/README.md',
  '+++ b/README.md',
  '@@ -1 +1 @@',
  '+docs',
].join('\n');

test('parseDiff splits a diff into one patch per file', () => {
  const files = parseDiff(DIFF);
  assert.equal(files.length, 2);
  assert.equal(files[0].file, 'src/core/decide.ts');
  assert.equal(files[1].file, 'README.md');
  assert.match(files[0].patch, /\+new/);
});

test('routeFiles reviews everything when there is no provider (fail open)', async () => {
  const routed = await routeFiles(null, parseDiff(DIFF));
  assert.equal(routed.length, 2);
  assert.ok(routed.every((r) => r.review === true));
  assert.match(routed[0].reason, /no JEV_API_KEY/);
});

test('routeFiles skips Jev entirely under the min-files gate', async () => {
  let calls = 0;
  const provider = { evaluate: async () => (calls++, { answers: {} }) };
  const routed = await routeFiles(provider, parseDiff(DIFF), 5);
  assert.equal(calls, 0);
  assert.ok(routed.every((r) => r.review === true));
});

test('routeFiles asks Jev per file and routes on the answers', async () => {
  const provider = {
    evaluate: async ({ state }) => ({
      answers:
        state.file === 'README.md'
          ? { depth: { type: 'score', score: 0.2, confidence: 0.9 } }
          : { depth: { type: 'score', score: 3, confidence: 0.9 }, lens: { type: 'choice', choice: 'correctness', confidence: 0.8 } },
    }),
  };
  const routed = await routeFiles(provider, parseDiff(DIFF), 0);
  const byFile = Object.fromEntries(routed.map((r) => [r.file, r]));
  assert.equal(byFile['src/core/decide.ts'].review, true);
  assert.equal(byFile['src/core/decide.ts'].lens, 'correctness');
  assert.equal(byFile['README.md'].review, false);
});
