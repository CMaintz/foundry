import assert from 'node:assert/strict';
import { test } from 'node:test';
import { CloudflareProvider, TypeSafeProvider, postJson, providerFromEnv } from './client.mjs';

const realFetch = globalThis.fetch;

function mockFetch(responses) {
  const calls = [];
  const queue = [...responses];
  globalThis.fetch = async (url, init) => {
    calls.push({ url, init });
    const r = queue.shift();
    return {
      ok: r.status >= 200 && r.status < 300,
      status: r.status,
      json: async () => r.body,
      text: async () => JSON.stringify(r.body ?? ''),
    };
  };
  return calls;
}

async function withMock(responses, fn) {
  const calls = mockFetch(responses);
  try {
    return await fn(calls);
  } finally {
    globalThis.fetch = realFetch;
  }
}

test('postJson posts JSON and parses the response', async () => {
  await withMock([{ status: 200, body: { hello: 'world' } }], async (calls) => {
    const out = await postJson('https://x/y', { Authorization: 'Bearer k' }, { a: 1 });
    assert.deepEqual(out, { hello: 'world' });
    assert.equal(calls[0].init.method, 'POST');
    assert.equal(calls[0].init.headers['Content-Type'], 'application/json');
    assert.equal(calls[0].init.headers.Authorization, 'Bearer k');
    assert.deepEqual(JSON.parse(calls[0].init.body), { a: 1 });
  });
});

test('postJson retries on 429 then succeeds', async () => {
  await withMock([{ status: 429 }, { status: 200, body: { ok: true } }], async (calls) => {
    const out = await postJson('https://x/y', {}, {});
    assert.deepEqual(out, { ok: true });
    assert.equal(calls.length, 2);
  });
});

test('postJson throws on a non-retryable status', async () => {
  await withMock([{ status: 500, body: 'boom' }], async () => {
    await assert.rejects(() => postJson('https://x/y', {}, {}, 1), /500/);
  });
});

test('TypeSafeProvider posts to /systemone with model and auth', async () => {
  await withMock([{ status: 200, body: { answers: {} } }], async (calls) => {
    await new TypeSafeProvider('key', 'jev-latest').evaluate({ state: { q: 1 }, questions: { a: {} } });
    assert.match(calls[0].url, /\/v1\/systemone$/);
    const body = JSON.parse(calls[0].init.body);
    assert.equal(body.model, 'jev-latest');
    assert.deepEqual(body.state, { q: 1 });
    assert.equal(calls[0].init.headers.Authorization, 'Bearer key');
  });
});

test('providerFromEnv returns null without a key (fail-open)', () => {
  assert.equal(providerFromEnv({}), null);
});

test('providerFromEnv builds a TypeSafe provider and honors the base-url override', () => {
  const p = providerFromEnv({ JEV_API_KEY: 'k', TYPESAFE_AI_BASE_URL: 'http://localhost:9/v1' });
  assert.ok(p instanceof TypeSafeProvider);
  assert.equal(p.baseUrl, 'http://localhost:9/v1');
  assert.equal(p.model, 'jev-latest');
});

test('providerFromEnv builds a Cloudflare provider, or null when the account is missing', () => {
  const p = providerFromEnv({ JEV_PROVIDER: 'cloudflare', JEV_API_KEY: 'k', CLOUDFLARE_ACCOUNT_ID: 'acc' });
  assert.ok(p instanceof CloudflareProvider);
  assert.equal(providerFromEnv({ JEV_PROVIDER: 'cloudflare', JEV_API_KEY: 'k' }), null);
});
