const CUSTOMER = Object.freeze({
  id: 1,
  name: 'Evaluation Sandbox Customer',
  username: 'maestro-evaluation',
  email: 'sandbox@example.invalid',
  phone: '+000-000-0000',
  website: 'example.invalid',
  company: { name: 'Processual Maestro Evaluation Sandbox' },
  address: {
    street: 'Qualification Lane',
    suite: 'Read Only',
    city: 'Sandbox',
    zipcode: '00000',
  },
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

export default {
  async fetch(request) {
    const url = new URL(request.url);
    const method = request.method.toUpperCase();

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
