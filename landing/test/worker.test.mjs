import test from 'node:test';
import assert from 'node:assert/strict';
import worker, { validateSignup } from '../src/worker.mjs';

const signup = { email: 'person@example.com', name: 'Sam', role: 'care-team', consent: true, website: '' };
const origin = 'https://atria.example.com';
const request = (data = signup, headers = {}) => new Request(`${origin}/api/waitlist`, {
  method: 'POST', headers: { Origin: origin, 'Content-Type': 'application/json', ...headers }, body: JSON.stringify(data),
});

test('preview redirects preserve paths and queries within the canonical origin', async () => {
  const env = { CANONICAL_ORIGIN: 'https://atria.atriveo.com' };
  for (const path of ['/', '/privacy?from=preview', '//other.invalid/path?from=preview']) {
    const response = await worker.fetch(new Request(`https://atria-landing.example.workers.dev${path}`), env);
    assert.equal(response.status, 308);
    const target = new URL(response.headers.get('Location'));
    assert.equal(target.origin, env.CANONICAL_ORIGIN);
    assert.equal(target.pathname + target.search, path);
  }
});

test('stale preview form submissions request a refresh without writing', async () => {
  const response = await worker.fetch(new Request('https://atria-landing.example.workers.dev/api/waitlist', {
    method: 'POST', body: JSON.stringify(signup),
  }), { CANONICAL_ORIGIN: 'https://atria.atriveo.com' });
  assert.equal(response.status, 409);
  assert.match((await response.json()).error, /Refresh/);
});

test('HTML preserves its status and cache policy while excluding edge script injection', async () => {
  const env = { ASSETS: { fetch: async () => new Response('<h1>Missing</h1>', {
    status: 404, headers: { 'Content-Type': 'text/html', 'Cache-Control': 'public, max-age=300', 'X-Content-Type-Options': 'nosniff' },
  }) } };
  const response = await worker.fetch(new Request(`${origin}/missing`), env);
  assert.equal(response.status, 404);
  assert.equal(await response.text(), '<h1>Missing</h1>');
  assert.equal(response.headers.get('Cache-Control'), 'public, max-age=300, no-transform');
  assert.equal(response.headers.get('X-Content-Type-Options'), 'nosniff');
  env.ASSETS.fetch = async () => new Response('script', { headers: { 'Content-Type': 'application/javascript', 'Cache-Control': 'public, max-age=300' } });
  assert.equal((await worker.fetch(new Request(`${origin}/app.js`), env)).headers.get('Cache-Control'), 'public, max-age=300');
});

test('normalizes emails and rejects invalid data and missing consent', () => {
  assert.equal(validateSignup({ ...signup, email: ' Person@Example.com ' }).value.email, 'person@example.com');
  for (const input of [null, [], {}, { ...signup, email: 'invalid' }, { ...signup, email: 'x\ny@example.com' }, { ...signup, consent: false }, { ...signup, role: 'admin' }, { ...signup, name: 'x'.repeat(101) }]) {
    assert.ok(validateSignup(input).error);
  }
});

test('persists a signup with parameters and confirms only a successful write', async () => {
  let saved;
  const env = { DB: { prepare(sql) {
    assert.match(sql, /ON CONFLICT\(email\) DO NOTHING/);
    assert.ok(!sql.includes(signup.email));
    return { bind(...values) { saved = values; return { run: async () => ({ success: true }) }; } };
  } } };
  const response = await worker.fetch(request(), env);
  assert.equal(response.status, 200);
  assert.deepEqual(await response.json(), { ok: true });
  assert.deepEqual(saved.slice(1), ['person@example.com', 'Sam', 'care-team', '2026-10-19']);
});

test('database failures never look like successful signups', async () => {
  for (const run of [async () => { throw new Error('DB unavailable'); }, async () => ({ success: false })]) {
    const env = { DB: { prepare: () => ({ bind: () => ({ run }) }) } };
    const response = await worker.fetch(request(), env);
    assert.equal(response.status, 503);
    assert.ok((await response.json()).error);
  }
  assert.equal((await worker.fetch(request(), {})).status, 503);
});

test('rejects cross-origin, wrong method, and wrong content type', async () => {
  assert.equal((await worker.fetch(request(signup, { Origin: 'https://other.example.com' }), {})).status, 403);
  assert.equal((await worker.fetch(new Request(`${origin}/api/waitlist`), {})).status, 405);
  assert.equal((await worker.fetch(request(signup, { 'Content-Type': 'text/plain' }), {})).status, 415);
});

test('rejects oversized streamed bodies and invalid JSON', async () => {
  assert.equal((await worker.fetch(request({ ...signup, name: 'x'.repeat(5000) }), {})).status, 413);
  const broken = new Request(`${origin}/api/waitlist`, { method: 'POST', headers: { Origin: origin, 'Content-Type': 'application/json' }, body: '{' });
  assert.equal((await worker.fetch(broken, {})).status, 400);
});

test('rate limit responds with retry timing before attempting a write', async () => {
  const response = await worker.fetch(request(), { SIGNUP_LIMITER: { limit: async () => ({ success: false }) } });
  assert.equal(response.status, 429);
  assert.equal(response.headers.get('Retry-After'), '60');
});

test('honeypot silently discards spam without storing it', async () => {
  const response = await worker.fetch(request({ ...signup, website: 'https://spam.example.com' }), {});
  assert.equal(response.status, 200);
});

test('unknown APIs return 404 and pages are served by the asset binding', async () => {
  assert.equal((await worker.fetch(new Request(`${origin}/api/unknown`), {})).status, 404);
  const response = await worker.fetch(new Request(`${origin}/privacy`), { ASSETS: { fetch: async () => new Response('Privacy') } });
  assert.equal(await response.text(), 'Privacy');
});
