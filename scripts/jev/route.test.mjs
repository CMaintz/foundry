import assert from 'node:assert/strict';
import { test } from 'node:test';
import { DEFAULT_CONFIG, reviewQuestions, routeReview, toolcallQuestion, triageToolcall } from './route.mjs';

const depth = (score, confidence) => ({ type: 'score', score, confidence });
const lens = (choice, confidence = 0.8) => ({ type: 'choice', choice, confidence, probabilities: {} });
const noul = (n) => ({ type: 'noul', noul: n });

test('high-depth hunk gets deep review and its lens', () => {
  const out = routeReview({ depth: depth(2.7, 0.86), lens: lens('correctness'), touches_security: noul(0.12) });
  assert.equal(out.review, true);
  assert.equal(out.lens, 'correctness');
  assert.equal(out.security, 0.12);
});

test('low-depth, confident hunk is skipped', () => {
  const out = routeReview({ depth: depth(1.0, 0.9) });
  assert.equal(out.review, false);
  assert.match(out.reason, /skip/);
});

test('low confidence forces review even when depth is below threshold', () => {
  const out = routeReview({ depth: depth(0.5, 0.4) });
  assert.equal(out.review, true);
  assert.match(out.reason, /confidence/);
});

test('a missing depth answer fails open to review', () => {
  const out = routeReview({});
  assert.equal(out.review, true);
});

test('lens routing can be disabled', () => {
  const cfg = { ...DEFAULT_CONFIG, review: { ...DEFAULT_CONFIG.review, routeByLens: false } };
  const out = routeReview({ depth: depth(3, 0.9), lens: lens('spec') }, cfg);
  assert.equal(out.lens, null);
});

test('tool-call risk warns but never holds by default', () => {
  const out = triageToolcall(noul(0.8));
  assert.equal(out.warn, true);
  assert.equal(out.hold, false);
});

test('hold fires only when holdAbove is configured', () => {
  const cfg = { ...DEFAULT_CONFIG, toolcall: { warnAbove: 0.5, holdAbove: 0.9 } };
  assert.equal(triageToolcall(noul(0.95), cfg).hold, true);
  assert.equal(triageToolcall(noul(0.6), cfg).hold, false);
});

test('a missing risk answer neither warns nor holds', () => {
  const out = triageToolcall(undefined);
  assert.equal(out.warn, false);
  assert.equal(out.hold, false);
  assert.equal(out.risk, null);
});

test('question templates carry the right primitive types', () => {
  const q = reviewQuestions();
  assert.equal(q.depth.type, 'score');
  assert.equal(q.lens.type, 'choice');
  assert.equal(q.touches_security.type, 'noul');
  assert.equal(toolcallQuestion().type, 'noul');
});
