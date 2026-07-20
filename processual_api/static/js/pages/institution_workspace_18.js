PAGES.institution = (() => {
  'use strict';

  const state = {
    account: null,
    subscription: null,
    readiness: null,
    requests: [],
    loading: true,
    error: '',
    creatingTrack: '',
    actionMessage: '',
  };

  const INTEGRATION_TRACKS = [
    {
      key: 'camara',
      title: 'CAMARA / GSMA Open Gateway',
      subtitle: 'Telecom capability exposure and operator API alignment',
      operations: [
        'Capability profile selection',
        'Consent and authorization references',
        'Sandbox endpoint qualification',
        'Conformance evidence package',
      ],
    },
    {
      key: 'tmforum',
      title: 'TM Forum Open APIs',
      subtitle: 'Standardized telecom business and operational API contracts',
      operations: [
        'Open API version mapping',
        'Contract and payload review',
        'CTK evidence attachment',
        'Operator-specific deviation record',
      ],
    },
    {
      key: 'operator',
      title: 'Operator-specific integration',
      subtitle: 'Institution and operator requirements outside common standards',
      operations: [
        'DNS and TLS reference package',
        'OAuth / OIDC profile review',
        'Network allowlist and callback review',
        'Sandbox scope and escalation contacts',
      ],
    },
  ];

  function esc(value) {
    return String(value == null ? '' : value).replace(/[&<>"']/g, (char) => ({
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#39;',
    })[char]);
  }

  function arr(value) {
    return Array.isArray(value) ? value : [];
  }

  function pill(text, tone) {
    return `<span class="iw18-pill ${tone || ''}">${esc(text)}</span>`;
  }

  function buildReadiness(account, subscription, requests) {
    const plan = String(subscription?.plan || subscription?.plan_id || '').toLowerCase();
    const enterpriseEligible = plan.includes('enterprise');
    const requestCount = requests.length;
    return {
      completeness_percent: enterpriseEligible ? Math.min(80, 42 + requestCount * 8) : Math.min(55, 25 + requestCount * 6),
      missing_customer_inputs: [
        'Select CAMARA, TM Forum or operator-specific integration path',
        'Provide client-safe API, DNS, TLS and technical contact references',
      ],
      missing_security_controls: [
        'Complete supervisor evidence review before sandbox qualification',
        'Keep credentials in the approved secure intake only',
      ],
      standard_profile: '',
      sandbox_ready: false,
      production_allowed: false,
      runtime_connector_approved: false,
      raw_secret_visible: false,
      organization_name: account?.organization_name || '',
    };
  }

  async function load() {
    state.loading = true;
    state.error = '';
    render();

    const results = await Promise.allSettled([
      CLIENT.get('/auth/me'),
      CLIENT.get('/settings/subscription'),
      CLIENT.get('/settings/client-requests'),
    ]);

    state.account = results[0].status === 'fulfilled' ? results[0].value : null;
    state.subscription = results[1].status === 'fulfilled' ? results[1].value : null;

    const requestPayload = results[2].status === 'fulfilled' ? results[2].value : {};
    state.requests = arr(requestPayload.latest_requests || requestPayload.requests || requestPayload.items || requestPayload);
    state.readiness = buildReadiness(state.account, state.subscription, state.requests);
    state.error = results
      .filter((result) => result.status === 'rejected')
      .map((result) => result.reason?.detail || result.reason?.message || 'unavailable')
      .join(', ');

    state.loading = false;
    render();
  }

  function completion() {
    const readiness = state.readiness || {};
    if (Number.isFinite(Number(readiness.completeness_percent))) {
      return Math.max(0, Math.min(100, Number(readiness.completeness_percent)));
    }
    return 25;
  }

  function actionRows() {
    const readiness = state.readiness || {};
    const items = [
      ...arr(readiness.missing_customer_inputs),
      ...arr(readiness.missing_security_controls),
    ];

    if (!items.length) {
      return '<div class="iw18-empty">No client-visible integration actions are currently available.</div>';
    }

    return items.slice(0, 6).map((item, index) => {
      const title = typeof item === 'string' ? item : item.title || item.name || 'Required action';
      const description = typeof item === 'object'
        ? item.description || item.status || 'Awaiting your input'
        : 'Provide the requested reference or clarification for supervisor review.';
      return `<div class="iw18-action"><strong>${String(index + 1).padStart(2, '0')} · ${esc(title)}</strong><span>${esc(description)}</span></div>`;
    }).join('');
  }

  function timeline() {
    const readiness = state.readiness || {};
    const sandbox = Boolean(readiness.sandbox_ready || readiness.pilot_ready);
    const steps = [
      ['Organization profile', 'Client-visible references only', 'complete'],
      ['Standards and API profile', 'CAMARA, TM Forum or operator-specific mapping', 'active'],
      ['Technical package', 'API, DNS, TLS, consent and contact references', 'active'],
      ['Supervisor review', 'Evidence and standards assessment', 'next'],
      ['Sandbox qualification', 'Contract and behavioral tests', sandbox ? 'complete' : 'locked'],
      ['Production review', 'Separate multi-party decision', 'locked'],
    ];

    return `<div class="iw18-timeline">${steps.map((step, index) => `
      <div class="iw18-step">
        <b>${index + 1}</b>
        <div><strong>${step[0]}</strong><span>${step[1]}</span></div>
        ${pill(step[2], step[2] === 'complete' ? 'good' : 'warn')}
      </div>`).join('')}</div>`;
  }

  function requestTrack(request) {
    const preview = String(request?.message_preview || '').toLowerCase();
    for (const track of INTEGRATION_TRACKS) {
      if (preview.includes(`integration_track=${track.key}`)) return track.key;
    }
    return '';
  }

  function requestForTrack(trackKey) {
    return state.requests.find((request) => requestTrack(request) === trackKey) || null;
  }

  function isActiveStatus(status) {
    return ['pending', 'reviewed', 'approved'].includes(String(status || '').toLowerCase());
  }

  function latestRequest() {
    const request = state.requests[0];
    if (!request) return 'No integration request submitted yet.';
    return `${request.request_type_label || request.request_type || 'Integration request'} · ${request.short_id || request.request_id || 'case'} · ${request.status || 'submitted'}`;
  }

  function trackStatus(trackKey) {
    const request = requestForTrack(trackKey);
    if (request) {
      const status = String(request.status || 'pending');
      return [`${request.short_id || 'Case'} · ${status}`, isActiveStatus(status) ? 'warn' : 'good'];
    }
    return ['Available for request', 'warn'];
  }

  function caseMessage(track) {
    return [
      '[STAGE18_INTEGRATION_CASE]',
      `integration_track=${track.key}`,
      `integration_standard=${track.title}`,
      'requested_phase=supervisor_review',
      'sandbox_requested=true',
      'production_allowed=false',
      'runtime_connector_approved=false',
      'No raw secrets are included. Please create a client-safe integration case and return the required evidence checklist.',
    ].join('\n');
  }

  async function createTrackCase(trackKey) {
    const track = INTEGRATION_TRACKS.find((item) => item.key === trackKey);
    if (!track || state.creatingTrack) return;

    const existing = requestForTrack(trackKey);
    if (existing && isActiveStatus(existing.status)) {
      state.actionMessage = `${track.title} already has an active case: ${existing.short_id || existing.request_id}.`;
      render();
      return;
    }

    state.creatingTrack = trackKey;
    state.actionMessage = `Creating ${track.title} case…`;
    render();

    try {
      const result = await CLIENT.post('/settings/client-request', {
        request_type: 'general_support',
        requested_plan: 'enterprise_integration',
        message: caseMessage(track),
      });
      const created = result?.request || {};
      state.actionMessage = `${track.title} case created: ${created.short_id || created.request_id || 'submitted'}.`;
      await load();
    } catch (error) {
      state.actionMessage = `Case creation failed: ${error?.detail || error?.message || 'unavailable'}`;
      state.creatingTrack = '';
      render();
    }
  }

  function integrationTracks() {
    return `<div class="iw18-grid">${INTEGRATION_TRACKS.map((track) => {
      const request = requestForTrack(track.key);
      const [status, tone] = trackStatus(track.key);
      const active = request && isActiveStatus(request.status);
      const busy = state.creatingTrack === track.key;
      return `<section class="iw18-panel" data-integration-track="${track.key}">
        <div class="iw18-status" style="justify-content:space-between;align-items:flex-start">
          <div>
            <h2>${esc(track.title)}</h2>
            <small>${esc(track.subtitle)}</small>
          </div>
          ${pill(status, tone)}
        </div>
        <div style="margin-top:.9rem">${track.operations.map((operation, index) => `
          <div class="iw18-action">
            <strong>${String(index + 1).padStart(2, '0')} · ${esc(operation)}</strong>
            <span>Reference submission and supervisor review only; no runtime activation from this page.</span>
          </div>`).join('')}</div>
        ${request ? `<div class="iw18-empty" style="margin-top:.8rem">Case ID: ${esc(request.request_id || request.short_id || '—')} · Status: ${esc(request.status || 'pending')}</div>` : ''}
        <div style="margin-top:.9rem">
          <button class="iw18-button ghost" data-create-track="${track.key}" ${active || busy ? 'disabled' : ''}>${busy ? 'Creating case…' : active ? 'Active case exists' : `Create ${esc(track.title)} case`}</button>
        </div>
      </section>`;
    }).join('')}</div>`;
  }

  function render() {
    const root = document.getElementById('institution-workspace-root');
    if (!root) return;

    if (state.loading) {
      root.innerHTML = '<div class="iw18-empty">Loading institution workspace…</div>';
      return;
    }

    const subscription = state.subscription || {};
    const readiness = state.readiness || {};
    const percentage = completion();
    const eligible = /enterprise/.test(String(subscription.plan || subscription.plan_id || '').toLowerCase());

    root.innerHTML = `<div class="iw18-shell">
      <section class="iw18-hero">
        <div class="iw18-eyebrow">Institution workspace · Stage 18 R2</div>
        <h1>${esc(state.account?.organization_name || 'Your institution integration workspace')}</h1>
        <p>Choose the relevant standards path, create a persisted integration case, submit client-safe technical references and follow supervisor review without exposing credentials or internal risk notes.</p>
        <div class="iw18-status">
          ${pill(eligible ? 'Enterprise eligible' : 'Enterprise review required', eligible ? 'good' : 'warn')}
          ${pill('CAMARA / TM Forum case workflow', 'good')}
          ${pill('No raw secrets', 'good')}
          ${pill('Production blocked', 'warn')}
        </div>
      </section>

      <section class="iw18-panel">
        <h2>Integration standards and operations</h2>
        <small>Create one persisted case per standards path. Case creation requests supervisor review only and never grants runtime or production access.</small>
        ${state.actionMessage ? `<div class="iw18-empty" style="margin-top:.8rem">${esc(state.actionMessage)}</div>` : ''}
      </section>

      ${integrationTracks()}

      <div class="iw18-grid">
        <section class="iw18-panel">
          <h2>Integration journey</h2>
          <small>One shared case model with standard-specific qualification steps.</small>
          <div class="iw18-progress"><span style="width:${percentage}%"></span></div>
          <div class="iw18-muted">${percentage}% readiness based on available client-safe checks</div>
          <div style="margin-top:1rem">${timeline()}</div>
        </section>

        <aside class="iw18-panel">
          <h2>Next actions</h2>
          <small>Only items assigned to your organization are shown.</small>
          ${actionRows()}
          <div style="margin-top:.9rem"><button class="iw18-button" data-open-settings>Open integration settings</button></div>
        </aside>
      </div>

      <div class="iw18-grid">
        <section class="iw18-panel">
          <h2>Current integration request</h2>
          <p class="iw18-muted">${esc(latestRequest())}</p>
          <button class="iw18-button ghost" data-open-settings>Review requests and supervisor messages</button>
        </section>

        <section class="iw18-panel">
          <h2>Credential and runtime status</h2>
          <p class="iw18-muted">Credential values are never displayed here. Maestro shows only validation, rotation and expiry status after an approved secure intake.</p>
          <div class="iw18-status">
            ${pill('Vault-backed reference only', 'good')}
            ${pill('Runtime disabled', 'warn')}
            ${pill('Sandbox approval required', 'warn')}
          </div>
        </section>
      </div>

      ${state.error ? `<div class="iw18-empty">Some client-safe data could not be loaded: ${esc(state.error)}</div>` : ''}
    </div>`;

    root.querySelectorAll('[data-open-settings]').forEach((button) => {
      button.addEventListener('click', () => document.querySelector('.nav-btn[data-page="settings"]')?.click());
    });
    root.querySelectorAll('[data-create-track]').forEach((button) => {
      button.addEventListener('click', () => createTrackCase(button.dataset.createTrack));
    });
  }

  return { init: load, refresh: load, createTrackCase };
})();
