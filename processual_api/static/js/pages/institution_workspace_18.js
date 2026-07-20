PAGES.institution = (() => {
  'use strict';

  const TRACKS = [
    {
      key: 'camara',
      caseType: 'camara_integration_case',
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
      caseType: 'tmforum_integration_case',
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
      caseType: 'operator_integration_case',
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

  const state = {
    account: null,
    subscription: null,
    requests: [],
    cases: [],
    loading: true,
    creatingTrack: '',
    actionMessage: '',
    error: '',
  };

  function esc(value) {
    return String(value == null ? '' : value).replace(/[&<>"']/g, (char) => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
    })[char]);
  }

  function arr(value) { return Array.isArray(value) ? value : []; }
  function pill(text, tone) { return `<span class="iw18-pill ${tone || ''}">${esc(text)}</span>`; }

  function markerValue(preview, key) {
    const match = String(preview || '').match(new RegExp(`(?:^|\\n)${key}=([^\\n]+)`));
    return match ? match[1].trim() : '';
  }

  function normalizeCase(request) {
    const preview = String(request?.message_preview || '');
    if (!preview.includes('[STAGE18_INTEGRATION_CASE]')) return null;
    const integrationTrack = markerValue(preview, 'integration_track');
    const track = TRACKS.find((item) => item.key === integrationTrack);
    if (!track) return null;
    return {
      id: request.request_id || request.id || '',
      short_id: request.short_id || '',
      case_type: track.caseType,
      case_label: track.title,
      integration_track: track.key,
      requested_phase: markerValue(preview, 'requested_phase') || 'supervisor_review',
      sandbox_requested: markerValue(preview, 'sandbox_requested') !== 'false',
      production_allowed: false,
      runtime_connector_approved: false,
      raw_secret_visible: false,
      status: request.status || 'pending',
      created_at: request.created_at || '',
      source_request_type: request.request_type || 'general_support',
    };
  }

  function activeCase(trackKey) {
    return state.cases.find((item) => item.integration_track === trackKey && ['pending', 'reviewed', 'approved'].includes(String(item.status).toLowerCase())) || null;
  }

  function caseMessage(track) {
    return [
      '[STAGE18_INTEGRATION_CASE]',
      `case_type=${track.caseType}`,
      `integration_track=${track.key}`,
      `integration_standard=${track.title}`,
      'requested_phase=supervisor_review',
      'sandbox_requested=true',
      'production_allowed=false',
      'runtime_connector_approved=false',
      'raw_secret_visible=false',
      'No raw secrets are included. Create a client-safe supervisor review case and return the evidence checklist.',
    ].join('\n');
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
    const payload = results[2].status === 'fulfilled' ? results[2].value : {};
    state.requests = arr(payload.latest_requests || payload.requests || payload.items || payload);
    state.cases = state.requests.map(normalizeCase).filter(Boolean);
    state.error = results.filter((item) => item.status === 'rejected')
      .map((item) => item.reason?.detail || item.reason?.message || 'unavailable').join(', ');
    state.loading = false;
    state.creatingTrack = '';
    render();
  }

  async function createTrackCase(trackKey) {
    const track = TRACKS.find((item) => item.key === trackKey);
    if (!track || state.creatingTrack) return;
    const existing = activeCase(trackKey);
    if (existing) {
      state.actionMessage = `${track.title} already has active case ${existing.short_id || existing.id}.`;
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
      state.actionMessage = `${track.caseType} created: ${created.short_id || created.request_id || 'submitted'}.`;
      await load();
    } catch (error) {
      state.creatingTrack = '';
      state.actionMessage = `Case creation failed: ${error?.detail || error?.message || 'unavailable'}`;
      render();
    }
  }

  function progress() {
    const plan = String(state.subscription?.plan || state.subscription?.plan_id || '').toLowerCase();
    const base = plan.includes('enterprise') ? 42 : 25;
    return Math.min(85, base + state.cases.length * 12);
  }

  function caseContract(item) {
    if (!item) return '';
    return `<div class="iw18-empty" style="margin-top:.8rem">
      <strong>Case ID: ${esc(item.id || item.short_id)}</strong><br>
      Type: ${esc(item.case_type)} · Track: ${esc(item.integration_track)} · Status: ${esc(item.status)}<br>
      Phase: ${esc(item.requested_phase)} · Sandbox requested: ${esc(item.sandbox_requested)}<br>
      Production allowed: false · Runtime connector approved: false · Raw secrets visible: false
    </div>`;
  }

  function trackCards() {
    return `<div class="iw18-grid">${TRACKS.map((track) => {
      const item = activeCase(track.key) || state.cases.find((entry) => entry.integration_track === track.key);
      const busy = state.creatingTrack === track.key;
      const active = Boolean(activeCase(track.key));
      const status = item ? `${item.short_id || 'Case'} · ${item.status}` : 'Available for request';
      return `<section class="iw18-panel" data-integration-track="${track.key}">
        <div class="iw18-status" style="justify-content:space-between;align-items:flex-start">
          <div><h2>${esc(track.title)}</h2><small>${esc(track.subtitle)}</small></div>
          ${pill(status, active ? 'warn' : item ? 'good' : 'warn')}
        </div>
        <div style="margin-top:.9rem">${track.operations.map((operation, index) => `
          <div class="iw18-action"><strong>${String(index + 1).padStart(2, '0')} · ${esc(operation)}</strong>
          <span>Reference submission and supervisor review only; no runtime activation from this page.</span></div>`).join('')}</div>
        ${caseContract(item)}
        <div style="margin-top:.9rem"><button class="iw18-button ghost" data-create-track="${track.key}" ${active || busy ? 'disabled' : ''}>
          ${busy ? 'Creating case…' : active ? 'Active case exists' : `Create ${esc(track.caseType)}`}
        </button></div>
      </section>`;
    }).join('')}</div>`;
  }

  function registry() {
    if (!state.cases.length) return '<div class="iw18-empty">No Stage 18 integration cases have been created.</div>';
    return `<div class="iw18-timeline">${state.cases.map((item, index) => `
      <div class="iw18-step"><b>${index + 1}</b><div><strong>${esc(item.case_type)}</strong>
      <span>${esc(item.short_id || item.id)} · ${esc(item.integration_track)} · ${esc(item.requested_phase)}</span></div>
      ${pill(item.status, ['completed', 'approved'].includes(String(item.status).toLowerCase()) ? 'good' : 'warn')}</div>`).join('')}</div>`;
  }

  function render() {
    const root = document.getElementById('institution-workspace-root');
    if (!root) return;
    if (state.loading) {
      root.innerHTML = '<div class="iw18-empty">Loading institution workspace…</div>';
      return;
    }
    const eligible = /enterprise/.test(String(state.subscription?.plan || state.subscription?.plan_id || '').toLowerCase());
    const pct = progress();
    root.innerHTML = `<div class="iw18-shell">
      <section class="iw18-hero">
        <div class="iw18-eyebrow">Institution workspace · Stage 18 R3</div>
        <h1>${esc(state.account?.organization_name || 'Your institution integration workspace')}</h1>
        <p>Create standards-specific integration cases with explicit client-safe contracts and supervisor-controlled qualification.</p>
        <div class="iw18-status">${pill(eligible ? 'Enterprise eligible' : 'Enterprise review required', eligible ? 'good' : 'warn')}
          ${pill('Explicit case contracts', 'good')}${pill('No raw secrets', 'good')}${pill('Production blocked', 'warn')}</div>
      </section>
      <section class="iw18-panel"><h2>Integration standards and operations</h2>
        <small>Each case exposes its type, track, phase and safety guardrails directly. Storage remains compatible with existing client requests.</small>
        ${state.actionMessage ? `<div class="iw18-empty" style="margin-top:.8rem">${esc(state.actionMessage)}</div>` : ''}
      </section>
      ${trackCards()}
      <div class="iw18-grid">
        <section class="iw18-panel"><h2>Institution case registry</h2><small>Client-safe projection of persisted Stage 18 cases.</small>${registry()}</section>
        <section class="iw18-panel"><h2>Integration readiness</h2><small>Supervisor review remains mandatory.</small>
          <div class="iw18-progress"><span style="width:${pct}%"></span></div><div class="iw18-muted">${pct}% readiness</div>
          <div class="iw18-status" style="margin-top:1rem">${pill('Sandbox requested, not granted', 'warn')}${pill('Runtime disabled', 'warn')}${pill('Vault references only', 'good')}</div>
        </section>
      </div>
      <div class="iw18-grid">
        <section class="iw18-panel"><h2>Next actions</h2><div class="iw18-action"><strong>01 · Supervisor evidence review</strong><span>Review API, DNS, TLS, consent and contact references.</span></div>
          <div class="iw18-action"><strong>02 · Sandbox qualification</strong><span>Run contract and behavioral checks only after approval.</span></div>
          <button class="iw18-button" data-open-settings>Open integration settings</button></section>
        <section class="iw18-panel"><h2>Credential and runtime status</h2><p class="iw18-muted">Credential values are never displayed here.</p>
          <div class="iw18-status">${pill('production_allowed=false', 'warn')}${pill('runtime_connector_approved=false', 'warn')}${pill('raw_secret_visible=false', 'good')}</div></section>
      </div>
      ${state.error ? `<div class="iw18-empty">Some client-safe data could not be loaded: ${esc(state.error)}</div>` : ''}
    </div>`;
    root.querySelectorAll('[data-create-track]').forEach((button) => button.addEventListener('click', () => createTrackCase(button.dataset.createTrack)));
    root.querySelectorAll('[data-open-settings]').forEach((button) => button.addEventListener('click', () => document.querySelector('.nav-btn[data-page="settings"]')?.click()));
  }

  return { init: load, refresh: load, createTrackCase, normalizeCase };
})();
