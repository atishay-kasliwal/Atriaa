const ROLES = new Set(['care-team', 'builder', 'partner', 'other']);
const MAX_BODY = 4096;

function json(body, status = 200, extraHeaders = {}) {
  return Response.json(body, {
    status,
    headers: { 'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff', ...extraHeaders },
  });
}

export function validateSignup(input) {
  if (!input || typeof input !== 'object' || Array.isArray(input)) return { error: 'Please complete the signup form.' };
  const email = typeof input.email === 'string' ? input.email.trim().toLowerCase() : '';
  const name = typeof input.name === 'string' ? input.name.trim() : '';
  if (email.length > 254 || !/^[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+$/.test(email)) return { error: 'Enter a valid email address.' };
  if (name.length > 100 || /[\u0000-\u001f]/.test(name)) return { error: 'Please use a name under 100 characters.' };
  if (!ROLES.has(input.role)) return { error: 'Choose the option that best describes you.' };
  if (input.consent !== true) return { error: 'Please agree to receive early-access updates.' };
  return { value: { email, name, role: input.role } };
}

async function readBody(request) {
  if (Number(request.headers.get('content-length')) > MAX_BODY) throw new Error('too_large');
  if (!request.body) throw new Error('invalid_json');
  const reader = request.body.getReader();
  const chunks = [];
  let length = 0;
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    length += value.byteLength;
    if (length > MAX_BODY) {
      await reader.cancel();
      throw new Error('too_large');
    }
    chunks.push(value);
  }
  const data = new Uint8Array(length);
  let offset = 0;
  for (const chunk of chunks) { data.set(chunk, offset); offset += chunk.length; }
  return JSON.parse(new TextDecoder().decode(data));
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (url.pathname === '/api/health' && request.method === 'GET') {
      return json({ status: 'ok', service: 'atria-landing' });
    }
    if (url.pathname !== '/api/waitlist') {
      if (url.pathname.startsWith('/api/')) return json({ error: 'Not found.' }, 404);
      return env.ASSETS.fetch(request);
    }
    if (request.method !== 'POST') return json({ error: 'Use the signup form to join.' }, 405, { Allow: 'POST' });
    const origin = request.headers.get('origin');
    if (origin !== url.origin) return json({ error: 'Please submit the form from the Atria website.' }, 403);
    if (!request.headers.get('content-type')?.toLowerCase().startsWith('application/json')) {
      return json({ error: 'Expected a JSON signup.' }, 415);
    }

    // Cloudflare supplies the connecting IP. It is used only as a transient
    // rate-limit key and is never stored in the waitlist database or logged.
    if (env.SIGNUP_LIMITER) {
      const { success } = await env.SIGNUP_LIMITER.limit({ key: request.headers.get('CF-Connecting-IP') || 'local' });
      if (!success) return json({ error: 'Too many attempts. Please try again in a minute.' }, 429, { 'Retry-After': '60' });
    }
    let input;
    try { input = await readBody(request); }
    catch (error) {
      return json({ error: error.message === 'too_large' ? 'The signup is too large.' : 'Please check the form and try again.' }, error.message === 'too_large' ? 413 : 400);
    }
    // A hidden field catches basic form spam without asking a visitor to solve a puzzle.
    if (input && typeof input === 'object' && input.website) return json({ ok: true });
    const parsed = validateSignup(input);
    if (parsed.error) return json({ error: parsed.error }, 400);
    if (!env.DB) return json({ error: 'Signup is temporarily unavailable. Please try again later.' }, 503);
    const { email, name, role } = parsed.value;
    try {
      const result = await env.DB.prepare(
        'INSERT INTO waitlist (id, email, name, role, consent_version) VALUES (?, ?, ?, ?, ?) ON CONFLICT(email) DO NOTHING',
      ).bind(crypto.randomUUID(), email, name, role, '2026-10-19').run();
      if (!result.success) throw new Error('write_failed');
      // New and existing entries get the same response; no email enumeration.
      return json({ ok: true });
    } catch {
      return json({ error: 'We couldn’t save your signup. Please try again in a moment.' }, 503);
    }
  },
};
