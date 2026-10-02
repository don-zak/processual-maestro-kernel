// Execute after a manually approved, SHA-pinned Cloudflare sandbox deployment.
// Only synthetic, project-owned endpoints are exercised. No credentials or raw responses are saved.
import assert from 'node:assert/strict';
import { mkdir, writeFile } from 'node:fs/promises';

const expectedSha = process.env.CHECKED_OUT_SHA;
assert.match(expectedSha || '', /^[0-9a-f]{40}$/, 'exact deployed source SHA required');
const base = (process.env.EVALUATION_WORKER_URL ||
  'https://processual-maestro-evaluation-sandbox.zaksam2030.workers.dev').replace(/\/$/, '');
const url = new URL(base);
assert.equal(url.protocol, 'https:', 'live sandbox requires HTTPS');
assert.equal(url.pathname, '/', 'sandbox base URL must have no path');
assert.equal(url.search, '', 'sandbox base URL must not contain a query');
assert.equal(url.hash, '', 'sandbox base URL must not contain a fragment');
assert.equal(url.hostname, 'processual-maestro-evaluation-sandbox.zaksam2030.workers.dev',
  'live verifier refuses requests outside the project-owned sandbox');
const results = [];
const evidencePath = process.env.GITHUB_WORKSPACE
  ? process.env.GITHUB_WORKSPACE + '/live-worker-evidence.json'
  : new URL('./live-worker-evidence.json', import.meta.url);

async function call(method, path, body) {
  const response = await fetch(base + path, {
    method,
    redirect: 'error',
    cache: 'no-store',
    signal: AbortSignal.timeout(10000),
    headers: body === undefined ? {} : { 'content-type': 'application/json' },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
  let payload = null;
  if (response.status === 403) {
    // Cloudflare Access may return HTML. Preserve only the status, never its body.
    return { response, payload };
  }
  if (method !== 'HEAD') {
    assert.match(response.headers.get('content-type') || '', /application\/json/i, path);
    payload = await response.json();
  }
  return { response, payload };
}
async function record(label, method, path, expectedStatus, required, expected) {
  const { response, payload } = await call(method, path);
  assert.equal(response.status, expectedStatus, label);
  if (required) for (const key of required) {
    assert.ok(Object.hasOwn(payload, key), label + ':' + key);
  }
  if (expected) for (const [key, value] of Object.entries(expected)) {
    assert.deepEqual(payload[key], value, label + ':' + key);
  }
  results.push({ label, status: response.status, pass: true });
  return payload;
}
async function draft(label, path, body) {
  const { response, payload } = await call('POST', path, body);
  assert.equal(response.status, 200, label);
  for (const key of ['synthetic', 'draft_only', 'review_required']) {
    assert.equal(payload[key], true, label + ':' + key);
  }
  for (const key of ['applied', 'production_mutation_performed', 'production_allowed']) {
    assert.equal(payload[key], false, label + ':' + key);
  }
  results.push({ label, status: response.status, pass: true });
  await record(label + '-missing-fields', 'POST', path, 422, ['detail'], {
    production_allowed: false, applied: false,
  }, {});
}
async function run() {
  // Cloudflare propagation can be briefly delayed after Wrangler returns.
  let live;
  let latestHttpStatus = null;
  let latestNetworkError = null;
  for (let attempt = 0; attempt < 6; attempt++) {
    try {
      const probe = await call('GET', '/health/live');
      latestHttpStatus = probe.response.status;
      latestNetworkError = null;
      if (probe.response.status === 200 && probe.payload?.deployment_sha === expectedSha) {
        live = probe.payload;
        break;
      }
    } catch (error) {
      // Only record the exception type; never persist a response or credentials.
      latestNetworkError = error?.name || 'NetworkError';
    }
    if (attempt < 5) await new Promise(resolve => setTimeout(resolve, 5000));
  }
  if (!live) {
    if (latestHttpStatus === 403) {
      throw new Error('WORKER_PUBLIC_ACCESS_DENIED_HTTP_403: inspect Cloudflare Access policies, workers.dev route, and approved deployment credentials before issuing any Evaluation keys');
    }
    if (latestHttpStatus === 200) {
      throw new Error('WORKER_SHA_MISMATCH: endpoint responded but did not attest the approved source SHA');
    }
    throw new Error('WORKER_HEALTH_UNVERIFIED: status=' +
      (latestHttpStatus ?? 'none') + '; transport=' + (latestNetworkError ?? 'none'));
  }
  assert.equal(live.production_allowed, false);
  results.push({ label: 'health-sha', status: 200, pass: true });

  const fixtures = [
    ['uni-student', '/university/requests/sandbox-student-request-001', ['request_id','student_id','request_text','status']],
    ['uni-course', '/university/courses/sandbox-course-001', ['course_id','title','description','requirements','schedule']],
    ['gov-case', '/government/cases/sandbox-public-case-001', ['case_id','citizen_id','status','history','audit_records']],
    ['gov-request', '/government/requests/sandbox-public-case-001', ['case_id','request_text','citizen_id','history','attachments']],
  ];
  for (const [label, path, fields] of fixtures) {
    await record(label, 'GET', path, 200, fields, { synthetic: true, production_allowed: false });
    const head = await call('HEAD', path);
    assert.equal(head.response.status, 200, label + '-head');
    results.push({ label: label + '-head', status: 200, pass: true });
  }
  await draft('uni-admission', '/university/admissions/sandbox-admission-001/response-draft',
    { case_id:'sandbox-admission-001', applicant_context:{application_status:'documents_received'} });
  await draft('gov-response', '/government/cases/sandbox-public-case-001/response-draft',
    { case_id:'sandbox-public-case-001', request_text:'Synthetic appointment inquiry' });
  await record('crm-read', 'GET', '/users/1', 200, ['id','account_status'], {});
  await record('billing-read', 'GET', '/billing/accounts/1', 200, ['account_id','currency'], {
    synthetic: true, production_allowed: false,
  });
  const crm = await call('POST', '/users/1/update-draft', {
    customer_id: 'sandbox-customer-001', proposed_changes: { segment: 'review' },
  });
  assert.equal(crm.response.status, 200);
  for (const key of ['draft_only','review_required']) assert.equal(crm.payload[key], true);
  for (const key of ['applied','production_mutation_performed','production_allowed']) {
    assert.equal(crm.payload[key], false);
  }
  results.push({ label: 'crm-draft-regression', status: 200, pass: true });
  await record('denied-method', 'PATCH', '/government/cases/sandbox-public-case-001', 405,
    ['detail'], { production_allowed: false });
  await record('unknown-route', 'GET', '/no-such-synthetic-fixture', 404,
    ['detail'], { production_allowed: false });
}
let failure = null;
try { await run(); } catch (error) { failure = String(error?.message || error); }
const evidence = {
  schema_version: 1,
  source_sha: expectedSha,
  worker_host: url.hostname,
  checked_at: new Date().toISOString(),
  qualification: failure ? 'fail' : 'pass',
  checks: results,
  // Avoid storing HTTP responses, user data, credentials, and task input.
  failure_reason: failure,
};
if (typeof evidencePath === 'string') await mkdir(process.env.GITHUB_WORKSPACE, { recursive: true });
await writeFile(evidencePath, JSON.stringify(evidence, null, 2) + '\n');
if (failure) throw new Error('Post-deploy Worker qualification failed: ' + failure);
console.log('PASS: exact-SHA live Worker attestation and ' + results.length + ' synthetic checks');
