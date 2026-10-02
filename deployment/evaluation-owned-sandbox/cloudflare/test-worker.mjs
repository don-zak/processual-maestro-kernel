// Run with Node.js 22 before any manual Cloudflare sandbox deployment.
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const source = await readFile(new URL('./worker.js', import.meta.url));
const { default: worker } = await import('data:text/javascript;base64,' + source.toString('base64'));
const base = 'https://sandbox.example.invalid';

async function request(method, path, body) {
  return worker.fetch(new Request(base + path, {
    method,
    ...(body === undefined ? {} : {
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(body),
    }),
  }));
}
async function fixture(path, fields) {
  const response = await request('GET', path);
  assert.equal(response.status, 200, path);
  const payload = await response.json();
  assert.equal(payload.production_allowed, false, path);
  assert.equal(payload.synthetic, true, path);
  for (const field of fields) assert.ok(payload[field] !== undefined, path + ':' + field);
  const head = await request('HEAD', path);
  assert.equal(head.status, 200);
  assert.equal(await head.text(), '');
}
async function draft(path, body) {
  let response = await request('POST', path, body);
  assert.equal(response.status, 200, path);
  const payload = await response.json();
  for (const key of ['draft_only', 'review_required', 'synthetic']) assert.equal(payload[key], true);
  for (const key of ['applied', 'production_mutation_performed', 'production_allowed']) assert.equal(payload[key], false);
  response = await request('POST', path, {});
  assert.equal(response.status, 422, path + ':missing fields');
}

await fixture('/university/requests/sandbox-student-request-001',
  ['request_id','student_id','request_text','status']);
await fixture('/university/courses/sandbox-course-001',
  ['course_id','title','description','requirements','schedule']);
await fixture('/government/cases/sandbox-public-case-001',
  ['case_id','citizen_id','status','history','audit_records']);
await fixture('/government/requests/sandbox-public-case-001',
  ['case_id','request_text']);
await draft('/university/admissions/sandbox-admission-001/response-draft',
  { case_id: 'sandbox-admission-001', applicant_context: { application_status: 'documents_received' } });
await draft('/government/cases/sandbox-public-case-001/response-draft',
  { case_id: 'sandbox-public-case-001', request_text: 'Synthetic inquiry' });

// Existing CRM/Billing scenarios must survive sector expansion.
assert.equal((await request('GET', '/users/1')).status, 200);
assert.equal((await request('GET', '/billing/accounts/1')).status, 200);
assert.equal((await request('POST', '/users/1/update-draft',
  { customer_id: 'sandbox-customer-001', proposed_changes: { segment: 'review' } })).status, 200);
assert.equal((await request('PATCH', '/government/cases/sandbox-public-case-001')).status, 405);
assert.equal((await request('GET', '/unknown')).status, 404);
console.log('PASS: six sector fixtures, reject paths, CRM/Billing regressions');
