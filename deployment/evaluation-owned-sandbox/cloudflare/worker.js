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


const STUDENT_REQUEST = Object.freeze({request_id:'sandbox-student-request-001',student_id:'sandbox-student-001',request_text:'Synthetic enrollment certificate inquiry',status:'open',synthetic:true,production_allowed:false});
const COURSE = Object.freeze({course_id:'sandbox-course-001',title:'Introduction to Systems',description:'Synthetic course',requirements:[],schedule:'Sandbox term',synthetic:true,production_allowed:false});
const PUBLIC_CASE = Object.freeze({case_id:'sandbox-public-case-001',citizen_id:'sandbox-citizen-001',status:'awaiting_review',history:[],audit_records:[],synthetic:true,production_allowed:false});
const PUBLIC_REQUEST = Object.freeze({case_id:'sandbox-public-case-001',request_text:'Synthetic appointment status inquiry',citizen_id:'sandbox-citizen-001',history:[],attachments:[],synthetic:true,production_allowed:false});

async function safeDraft(request, fields, kind) {
  let payload;
  try { payload = await request.json(); } catch {
    return json(400,{detail:'invalid_json',draft_only:true,applied:false,review_required:true,production_mutation_performed:false,production_allowed:false});
  }
  if (!payload || typeof payload !== 'object' || Array.isArray(payload) || fields.some(k=>payload[k]==null)) {
    return json(422,{detail:'draft_required_fields_missing',draft_only:true,applied:false,review_required:true,production_mutation_performed:false,production_allowed:false});
  }
  return json(200,{draft_id:'sandbox-'+kind+'-001',...Object.fromEntries(fields.map(k=>[k,payload[k]])),draft_only:true,applied:false,review_required:true,production_mutation_performed:false,production_allowed:false,synthetic:true});
}

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
      review_required: true,
      applied: false,
      production_mutation_performed: false,
      production_allowed: false,
    });
  }
  if (!body || typeof body !== 'object' || !body.customer_id || body.proposed_changes == null) {
    return json(422, {
      detail: 'customer_id_and_proposed_changes_required',
      draft_only: true,
      review_required: true,
      applied: false,
      production_mutation_performed: false,
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
    production_mutation_performed: false,
    production_allowed: false,
  });
}

export default {
  async fetch(request, env = {}) {
    const url = new URL(request.url);
    const method = request.method.toUpperCase();

    if (method === 'POST' && url.pathname === '/users/1/update-draft') {
      return draftCustomerUpdate(request);
    }
    if (method === 'POST' && url.pathname === '/university/admissions/sandbox-admission-001/response-draft') {
      return safeDraft(request,['case_id','applicant_context'],'admission');
    }
    if (method === 'POST' && url.pathname === '/government/cases/sandbox-public-case-001/response-draft') {
      return safeDraft(request,['case_id','request_text'],'government');
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
        deployment_sha: env.DEPLOYMENT_SHA || null,
        production_allowed: false,
      });
    } else if (url.pathname === '/users/1') {
      response = json(200, CUSTOMER);
    } else if (url.pathname === '/billing/accounts/1') {
      response = json(200, BILLING_ACCOUNT);
    } else if (url.pathname === '/university/requests/sandbox-student-request-001') {
      response = json(200, STUDENT_REQUEST);
    } else if (url.pathname === '/university/courses/sandbox-course-001') {
      response = json(200, COURSE);
    } else if (url.pathname === '/government/cases/sandbox-public-case-001') {
      response = json(200, PUBLIC_CASE);
    } else if (url.pathname === '/government/requests/sandbox-public-case-001') {
      response = json(200, PUBLIC_REQUEST);
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
