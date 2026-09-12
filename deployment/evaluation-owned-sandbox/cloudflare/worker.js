const CUSTOMER = Object.freeze({
  id: 1,
  name: 'Evaluation Sandbox Customer',
  username: 'maestro-evaluation',
  email: 'sandbox@example.invalid',
  phone: '+000-000-0000',
  website: 'example.invalid',
  account_status: 'active',
  segment: 'evaluation',
  company: { name: 'Processual Maestro Evaluation Sandbox' },
  address: {
    street: 'Qualification Lane',
    suite: 'Read Only',
    city: 'Sandbox',
    zipcode: '00000',
  },
});

const BILLING_ACCOUNT = Object.freeze({
  account_id: 'sandbox-account-001',
  balance: 128.5,
  currency: 'USD',
  invoice_status: 'current',
  payment_status: 'paid',
  synthetic: true,
  production_allowed: false,
});

const JSON_HEADERS = Object.freeze({
  'content-type': 'application/json; charset=utf-8',
  'cache-control': 'no-store',
  'x-content-type-options': 'nosniff',
});

function json(status, payload) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: JSON_HEADERS,
  });
}

async function draftCustomerUpdate(request) {
  let body;
  try {
    body = await request.json();
  } catch {
    return json(400, {
      detail: 'invalid_json',
      draft_only: true,
      applied: false,
      production_allowed: false,
    });
  }
  if (!body || typeof body !== 'object' || !body.customer_id || body.proposed_changes == null) {
    return json(422, {
      detail: 'customer_id_and_proposed_changes_required',
      draft_only: true,
      applied: false,
      production_allowed: false,
    });
  }
  return json(200, {
    draft_id: 'crm-draft-evaluation-001',
    customer_id: body.customer_id,
    proposed_changes: body.proposed_changes,
    draft_only: true,
    applied: false,
    review_required: true,
    production_allowed: false,
  });
}

export default {
  async fetch(request) {
    const url = new URL(request.url);
    const method = request.method.toUpperCase();

    if (method === 'POST' && url.pathname === '/users/1/update-draft') {
      return draftCustomerUpdate(request);
    }
    if (!['GET', 'HEAD'].includes(method)) {
      return json(405, {
        detail: 'read_only_sandbox',
        production_allowed: false,
      });
    }

    let response;
    if (url.pathname === '/health/live') {
      response = json(200, {
        status: 'live',
        service: 'processual-maestro-evaluation-sandbox',
        provider: 'cloudflare-workers',
        production_allowed: false,
      });
    } else if (url.pathname === '/users/1') {
      response = json(200, CUSTOMER);
    } else if (url.pathname === '/billing/accounts/1') {
      response = json(200, BILLING_ACCOUNT);
    } else {
      response = json(404, {
        detail: 'not_found',
        production_allowed: false,
      });
    }

    if (method === 'HEAD') {
      return new Response(null, {
        status: response.status,
        headers: response.headers,
      });
    }
    return response;
  },
};
