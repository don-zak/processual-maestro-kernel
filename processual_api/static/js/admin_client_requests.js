(function () {
  const ENDPOINT = '/settings/admin/client-requests';
  const DETAIL_ENDPOINT_PREFIX = '/settings/admin/client-requests/';
  const PAGE_ID = 'page-admin-clients';
  const HOST_ID = 'admin-client-requests-host';
  const CARD_ID = 'admin-client-requests-card';
  const STYLE_ID = 'admin-client-requests-style';

  const FIELDS = [
    'request_id',
    'short_id',
    'client_id',
    'request_type',
    'requested_plan',
    'status',
    'created_at',
    'source',
  ];

  let lastLoadAt = 0;
  let scheduledRefresh = 0;

  function byId(id) {
    return document.getElementById(id);
  }

  function text(value) {
    return String(value ?? '');
  }

  function clear(node) {
    if (!node) return;
    while (node.firstChild) {
      node.removeChild(node.firstChild);
    }
  }

  function appendText(parent, tagName, value, className) {
    const node = document.createElement(tagName);
    if (className) node.className = className;
    node.textContent = text(value);
    parent.appendChild(node);
    return node;
  }

  function installStyles() {
    if (byId(STYLE_ID)) return;

    const style = document.createElement('style');
    style.id = STYLE_ID;
    style.textContent = `
      #admin-client-requests-host {
        margin-bottom: var(--s-5);
      }

      #admin-client-requests-card {
        overflow: hidden;
      }

      .admin-client-requests-topline {
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: var(--s-3);
        flex-wrap: wrap;
      }

      .admin-client-requests-summary {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
        gap: var(--s-3);
        margin-top: var(--s-3);
      }

      .admin-client-requests-summary .mono-block {
        min-height: 74px;
      }

      .admin-client-request-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
        gap: var(--s-3);
        margin-top: var(--s-4);
      }

      .admin-client-request-row {
        border: 1px solid rgba(120, 150, 210, 0.28);
        border-radius: 14px;
        padding: var(--s-3);
        background: rgba(6, 12, 24, 0.28);
        min-width: 0;
      }

      .admin-client-request-head {
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: var(--s-3);
        margin-bottom: var(--s-3);
      }

      .admin-client-request-title {
        font-weight: 700;
        letter-spacing: 0.04em;
        overflow-wrap: anywhere;
      }

      .admin-client-request-status {
        white-space: nowrap;
        border: 1px solid rgba(120, 150, 210, 0.35);
        border-radius: 999px;
        padding: 2px 8px;
        font-size: 11px;
      }

      .admin-client-request-meta {
        display: grid;
        grid-template-columns: 112px minmax(0, 1fr);
        gap: 6px 10px;
        font-size: 12px;
      }

      .admin-client-request-meta-key {
        opacity: 0.72;
      }

      .admin-client-request-meta-value {
        overflow-wrap: anywhere;
      }

      .admin-client-request-actions {
        margin-top: var(--s-3);
        display: flex;
        justify-content: flex-end;
      }
    `;
    document.head.appendChild(style);
  }

  function authHeaders(extra) {
    const auth = window.PMK_ADMIN_AUTH;
    if (auth && typeof auth.headers === 'function') {
      return { ...auth.headers(), ...(extra || {}) };
    }

    const token =
      localStorage.getItem('access_token') ||
      localStorage.getItem('auth_token') ||
      localStorage.getItem('admin_token') ||
      sessionStorage.getItem('access_token') ||
      sessionStorage.getItem('auth_token') ||
      sessionStorage.getItem('admin_token');

    return {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(extra || {}),
    };
  }

  async function request(path) {
    const response = await fetch(path, {
      method: 'GET',
      credentials: 'include',
      headers: authHeaders({ Accept: 'application/json' }),
    });

    const rawText = await response.text();
    let data = {};
    if (rawText) {
      try {
        data = JSON.parse(rawText);
      } catch {
        data = { message: rawText };
      }
    }

    if (!response.ok) {
      const detail =
        data && typeof data === 'object'
          ? data.detail || data.message || `HTTP ${response.status}`
          : `HTTP ${response.status}`;
      throw new Error(detail);
    }

    return data;
  }

  function ensureHost() {
    const page = byId(PAGE_ID);
    if (!page) return null;

    let host = byId(HOST_ID);
    if (host) return host;

    host = document.createElement('div');
    host.id = HOST_ID;

    const wrapper = page.firstElementChild || page;
    wrapper.insertBefore(host, wrapper.firstChild);

    return host;
  }

  function ensureCard() {
    installStyles();

    const host = ensureHost();
    if (!host) return null;

    let card = byId(CARD_ID);
    if (card && card.parentNode !== host) {
      host.appendChild(card);
      return card;
    }

    if (card) return card;

    card = document.createElement('div');
    card.id = CARD_ID;
    card.className = 'card';
    card.dataset.adminClientRequestsCard = '1';

    card.innerHTML = [
      '<div class="admin-client-requests-topline sec-hdr">',
      '<div>',
      '<div class="sh-title">Client Requests Inbox</div>',
      '<div class="sh-sub">Read-only supervisor view of client request summaries</div>',
      '</div>',
      '<button id="admin-client-requests-refresh-btn" class="btn sm" type="button">Refresh Requests</button>',
      '</div>',
      '<div class="admin-client-requests-summary">',
      '<div id="admin-client-requests-status" class="mono-block" style="font-size:11px;white-space:pre-wrap">Client request inbox not loaded yet.</div>',
      '<div id="admin-client-requests-counts" class="mono-block" style="font-size:11px;white-space:pre-wrap"></div>',
      '</div>',
      '<div id="admin-client-requests-list"></div>',
      '<div id="admin-client-request-detail">',
      '<div class="admin-client-request-detail-title">Request Detail</div>',
      '<div id="admin-client-request-detail-status" class="mono-block" style="font-size:11px;white-space:pre-wrap">Select a request to view details.</div>',
      '<div id="admin-client-request-detail-body" style="margin-top:var(--s-3)"></div>',
      '</div>',
    ].join('');

    host.appendChild(card);
    return card;
  }

  function renderCounts(counts) {
    const target = byId('admin-client-requests-counts');
    clear(target);
    if (!target) return;

    const entries = Object.entries(counts || {});
    if (entries.length === 0) {
      target.textContent = 'status_counts: none';
      return;
    }

    target.textContent = entries
      .map(([key, value]) => `${key}: ${value}`)
      .join('\n');
  }

  function appendMeta(row, key, value) {
    appendText(row, 'div', key, 'admin-client-request-meta-key');
    appendText(row, 'div', value, 'admin-client-request-meta-value');
  }

  function renderRequestCard(item) {
    const row = document.createElement('div');
    row.className = 'admin-client-request-row';
    row.dataset.requestId = text(item?.request_id || '');

    const head = document.createElement('div');
    head.className = 'admin-client-request-head';

    const title = document.createElement('div');
    title.className = 'admin-client-request-title';
    title.textContent = text(item?.request_type || 'client_request');

    const status = document.createElement('div');
    status.className = 'admin-client-request-status';
    status.textContent = text(item?.status || 'pending');

    head.appendChild(title);
    head.appendChild(status);
    row.appendChild(head);

    const meta = document.createElement('div');
    meta.className = 'admin-client-request-meta';
    appendMeta(meta, 'request_id', item?.request_id || '');
    appendMeta(meta, 'short_id', item?.short_id || '');
    appendMeta(meta, 'client_id', item?.client_id || '');
    appendMeta(meta, 'requested_plan', item?.requested_plan || '');
    appendMeta(meta, 'created_at', item?.created_at || '');
    appendMeta(meta, 'source', item?.source || '');
    row.appendChild(meta);

    const actions = document.createElement('div');
    actions.className = 'admin-client-request-actions';

    const button = document.createElement('button');
    button.className = 'btn secondary sm admin-client-request-select';
    button.type = 'button';
    button.dataset.requestId = text(item?.request_id || '');
    button.textContent = 'Select';

    actions.appendChild(button);
    row.appendChild(actions);

    return row;
  }

  function renderList(requests) {
    const target = byId('admin-client-requests-list');
    clear(target);
    if (!target) return;

    if (!Array.isArray(requests) || requests.length === 0) {
      appendText(target, 'div', 'No client requests found.', 'admin-note');
      return;
    }

    const grid = document.createElement('div');
    grid.className = 'admin-client-request-grid';

    requests.forEach((item) => {
      grid.appendChild(renderRequestCard(item));
    });

    target.appendChild(grid);
  }



  async function postJson(path, payload) {
    const response = await fetch(path, {
      method: 'POST',
      credentials: 'include',
      headers: authHeaders({
        Accept: 'application/json',
        'Content-Type': 'application/json',
      }),
      body: JSON.stringify(payload || {}),
    });

    const rawText = await response.text();
    let data = {};
    if (rawText) {
      try {
        data = JSON.parse(rawText);
      } catch {
        data = { message: rawText };
      }
    }

    if (!response.ok) {
      const detail =
        data && typeof data === 'object'
          ? data.detail || data.message || `HTTP ${response.status}`
          : `HTTP ${response.status}`;
      throw new Error(detail);
    }

    return data;
  }
  function detailPath(requestId) {
    return DETAIL_ENDPOINT_PREFIX + encodeURIComponent(text(requestId));
  }

  function statusPath(requestId) {
    return detailPath(requestId) + '/status';
  }



  function responseDraftPath(requestId) {
    return detailPath(requestId) + '/response-draft';
  }


  function supervisorResponsePath(requestId) {
    return detailPath(requestId) + '/supervisor-response';
  }

  function renderAdminClientRequestStatusActions(detail, parent) {
    const requestId = text(detail?.request_id || '');
    if (!requestId) return;

    const actions = document.createElement('div');
    actions.id = 'admin-client-request-status-actions';
    actions.className = 'admin-client-request-status-actions';
    actions.style.marginTop = 'var(--s-3)';
    actions.style.display = 'flex';
    actions.style.gap = 'var(--s-2)';
    actions.style.flexWrap = 'wrap';

    const options = [
      ['reviewed', 'Mark Reviewed'],
      ['approved', 'Approve'],
      ['rejected', 'Reject'],
      ['completed', 'Complete'],
    ];

    options.forEach(([nextStatus, label]) => {
      const button = document.createElement('button');
      button.className = 'btn secondary sm admin-client-request-status-action';
      button.type = 'button';
      button.dataset.requestId = requestId;
      button.dataset.nextStatus = nextStatus;
      button.textContent = label;
      actions.appendChild(button);
    });

    parent.appendChild(actions);
  }
  function renderTimeline(detail, parent) {
    const timeline = Array.isArray(detail?.timeline) ? detail.timeline : [];
    appendText(parent, 'div', 'timeline', 'admin-client-request-detail-title');

    const list = document.createElement('div');
    list.className = 'admin-client-request-timeline';

    if (timeline.length === 0) {
      appendText(list, 'div', 'No timeline entries returned.', 'admin-note');
    }

    timeline.forEach((item) => {
      const node = document.createElement('div');
      node.className = 'admin-client-request-timeline-item';
      node.textContent = [
        text(item?.status || 'pending'),
        text(item?.at || ''),
        text(item?.source || ''),
      ]
        .filter(Boolean)
        .join(' | ');
      list.appendChild(node);
    });

    parent.appendChild(list);
  }


  function latestSupervisorResponseDraft(detail) {
    const drafts = Array.isArray(detail?.supervisor_response_drafts)
      ? detail.supervisor_response_drafts
      : [];
    return drafts.length ? drafts[drafts.length - 1] : null;
  }

  function setAdminClientRequestResponseDraftStatus(message) {
    const target = byId('admin-client-request-response-draft-status');
    if (target) {
      target.textContent = message;
    }
  }

  function adminClientRequestSupervisorResponses(detail) {
    return Array.isArray(detail?.supervisor_responses)
      ? detail.supervisor_responses
      : [];
  }

  function latestAdminClientRequestSupervisorResponse(detail) {
    const responses = adminClientRequestSupervisorResponses(detail);
    return responses.length ? responses[responses.length - 1] : null;
  }

  function adminClientRequestSupervisorResponseForDraft(detail, draftId) {
    const safeDraftId = text(draftId || '');
    if (!safeDraftId) return null;
    const responses = adminClientRequestSupervisorResponses(detail);
    for (let index = responses.length - 1; index >= 0; index -= 1) {
      const response = responses[index];
      if (text(response?.draft_id || '') === safeDraftId) {
        return response;
      }
    }
    return null;
  }

  function renderAdminClientRequestSentResponseSummary(detail, parent) {
    if (!parent) return;

    const responses = adminClientRequestSupervisorResponses(detail);
    const latestResponse = latestAdminClientRequestSupervisorResponse(detail);

    const summary = document.createElement('pre');
    summary.id = 'admin-client-request-supervisor-response-summary';
    summary.className = 'admin-client-request-supervisor-response-summary';

    if (!responses.length) {
      summary.textContent = 'Sent responses: 0';
    } else {
      summary.textContent = [
        'Sent responses: ' + String(responses.length),
        'Last sent response: ' +
          text(latestResponse?.sent_at || latestResponse?.response_id || ''),
        text(latestResponse?.body || ''),
      ]
        .filter(Boolean)
        .join('\n');
    }

    parent.appendChild(summary);
  }

  function renderAdminClientRequestResponseDraftPanel(detail, parent) {
    const requestId = detail?.request_id || detail?.short_id || '';
    if (!parent || !requestId) return;

    const latestDraft = latestSupervisorResponseDraft(detail);
    const sentDraftResponse = adminClientRequestSupervisorResponseForDraft(
      detail,
      latestDraft?.draft_id || ''
    );
    const isLatestDraftSent = Boolean(sentDraftResponse);
    const section = document.createElement('section');
    section.id = 'admin-client-request-response-draft';
    section.className = 'admin-client-request-response-draft';

    const title = document.createElement('h3');
    title.textContent = 'Supervisor Response Draft';
    section.appendChild(title);

    const help = document.createElement('p');
    help.className = 'muted';
    help.textContent = isLatestDraftSent
      ? 'This draft was already sent. Generate new response to continue safely.'
      : 'Draft, review, save, then send a supervisor response to the client timeline.';
    section.appendChild(help);

    const textarea = document.createElement('textarea');
    textarea.id = 'admin-client-request-response-draft-body';
    textarea.className = 'admin-client-request-response-draft-body';
    textarea.rows = 6;
    textarea.value = text(latestDraft?.body || '');
    textarea.dataset.draftId = text(latestDraft?.draft_id || '');
    textarea.placeholder = 'Generate or write a safe supervisor response draft.';
    section.appendChild(textarea);

    const actions = document.createElement('div');
    actions.className = 'admin-client-request-response-draft-actions';

    const generate = document.createElement('button');
    generate.id = 'admin-client-request-response-draft-generate';
    generate.className =
      'secondary-btn admin-client-request-response-draft-action admin-client-request-response-draft-generate';
    generate.type = 'button';
    generate.textContent = isLatestDraftSent ? 'Generate new response' : 'Generate Draft';
    generate.addEventListener('click', () => {
      generateAdminClientRequestResponseDraft(requestId);
    });
    actions.appendChild(generate);

    const save = document.createElement('button');
    save.id = 'admin-client-request-response-draft-save';
    save.className =
      'primary-btn admin-client-request-response-draft-action admin-client-request-response-draft-save';
    save.type = 'button';
    save.textContent = 'Save Draft';
    save.addEventListener('click', () => {
      saveAdminClientRequestResponseDraft(requestId);
    });
    actions.appendChild(save);

    const send = document.createElement('button');
    send.id = 'admin-client-request-response-draft-send';
    send.className =
      'primary-btn admin-client-request-response-draft-action admin-client-request-response-draft-send';
    send.type = 'button';
    send.textContent = 'Send Response';
    send.disabled = isLatestDraftSent;
    if (isLatestDraftSent) {
      send.title = 'This draft was already sent. Generate new response before sending again.';
    }
    send.addEventListener('click', () => {
      sendAdminClientRequestSupervisorResponse(requestId);
    });
    actions.appendChild(send);

    const copy = document.createElement('button');
    copy.id = 'admin-client-request-response-draft-copy';
    copy.className =
      'secondary-btn admin-client-request-response-draft-action admin-client-request-response-draft-copy';
    copy.type = 'button';
    copy.textContent = 'Copy Draft';
    copy.addEventListener('click', () => {
      copyAdminClientRequestResponseDraft();
    });
    actions.appendChild(copy);

    section.appendChild(actions);

    const status = document.createElement('pre');
    status.id = 'admin-client-request-response-draft-status';
    status.className = 'admin-client-request-response-draft-status';
    status.textContent = isLatestDraftSent
      ? 'Already sent: ' + text(sentDraftResponse?.sent_at || sentDraftResponse?.response_id || '')
      : latestDraft
        ? 'Draft saved: ' + text(latestDraft.updated_at || latestDraft.created_at || '')
        : 'No saved draft yet.';
    section.appendChild(status);
    renderAdminClientRequestSentResponseSummary(detail, section);

    parent.appendChild(section);
  }

  async function generateAdminClientRequestResponseDraft(requestId) {
    setAdminClientRequestResponseDraftStatus(
      'Generating draft for request ' + text(requestId) + ' ...'
    );

    try {
      const data = await postJson(responseDraftPath(requestId), {
        mode: 'generate',
      });
      renderAdminClientRequestDetail(data?.request || {});
      setAdminClientRequestResponseDraftStatus(
        'Generated draft for request ' + text(requestId) + '.'
      );
      return data;
    } catch (error) {
      setAdminClientRequestResponseDraftStatus(
        'Failed to generate draft: ' +
          (error && error.message ? error.message : String(error))
      );
      return null;
    }
  }

  async function saveAdminClientRequestResponseDraft(requestId, body) {
    const textarea = byId('admin-client-request-response-draft-body');
    const draftBody =
      typeof body === 'string' ? body : textarea && textarea.value ? textarea.value : '';

    setAdminClientRequestResponseDraftStatus(
      'Saving draft for request ' + text(requestId) + ' ...'
    );

    try {
      const data = await postJson(responseDraftPath(requestId), {
        mode: 'manual',
        draft: draftBody,
        note: 'Saved from Admin request detail panel.',
      });
      renderAdminClientRequestDetail(data?.request || {});
      setAdminClientRequestResponseDraftStatus(
        'Draft saved for request ' + text(requestId) + '.'
      );
      return data;
    } catch (error) {
      setAdminClientRequestResponseDraftStatus(
        'Failed to save draft: ' +
          (error && error.message ? error.message : String(error))
      );
      return null;
    }
  }


  async function sendAdminClientRequestSupervisorResponse(requestId, body) {
    const textarea = byId('admin-client-request-response-draft-body');
    const draftBody =
      typeof body === 'string' ? body : textarea && textarea.value ? textarea.value : '';
    const draftId = textarea?.dataset?.draftId || '';

    setAdminClientRequestResponseDraftStatus(
      'Sending supervisor response for request ' + text(requestId) + ' ...'
    );

    try {
      const data = await postJson(supervisorResponsePath(requestId), {
        body: draftBody,
        draft_id: draftId,
      });
      renderAdminClientRequestDetail(data?.request || {});
      await loadAdminClientRequests(true);
      if (data?.status === 'already_sent') {
        setAdminClientRequestResponseDraftStatus(
          'already_sent: Response already sent for request ' + text(requestId) + '.'
        );
      } else {
        setAdminClientRequestResponseDraftStatus(
          'supervisor_response_sent: Sent response for request ' + text(requestId) + '.'
        );
      }
      return data;
    } catch (error) {
      setAdminClientRequestResponseDraftStatus(
        'Failed to send supervisor response: ' +
          (error && error.message ? error.message : String(error))
      );
      return null;
    }
  }

  async function copyAdminClientRequestResponseDraft() {
    const textarea = byId('admin-client-request-response-draft-body');
    const value = textarea && textarea.value ? textarea.value : '';
    if (!value) {
      setAdminClientRequestResponseDraftStatus('No draft text to copy.');
      return false;
    }

    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(value);
      } else {
        textarea.focus();
        textarea.select();
        document.execCommand('copy');
      }
      setAdminClientRequestResponseDraftStatus('Draft copied.');
      return true;
    } catch (error) {
      setAdminClientRequestResponseDraftStatus(
        'Failed to copy draft: ' +
          (error && error.message ? error.message : String(error))
      );
      return false;
    }
  }


  function renderAdminClientRequestDetail(detail) {
    ensureCard();

    const statusTarget = byId('admin-client-request-detail-status');
    const body = byId('admin-client-request-detail-body');

    if (statusTarget) {
      statusTarget.textContent =
        'Loaded detail for ' + text(detail?.request_id || detail?.short_id || '');
    }

    clear(body);
    if (!body) return;

    const grid = document.createElement('div');
    grid.className = 'admin-client-request-detail-grid';

    appendMeta(grid, 'request_id', detail?.request_id || '');
    appendMeta(grid, 'short_id', detail?.short_id || '');
    appendMeta(grid, 'client_id', detail?.client_id || '');
    appendMeta(grid, 'user_id', detail?.user_id || '');
    appendMeta(grid, 'role', detail?.role || '');
    appendMeta(grid, 'request_type', detail?.request_type || '');
    appendMeta(grid, 'request_label', detail?.request_label || '');
    appendMeta(grid, 'requested_plan', detail?.requested_plan || '');
    appendMeta(grid, 'status', detail?.status || '');
    appendMeta(grid, 'source', detail?.source || '');
    appendMeta(grid, 'created_at', detail?.created_at || '');
    appendMeta(grid, 'updated_at', detail?.updated_at || '');
    appendMeta(grid, 'message', detail?.message || '');
    appendMeta(grid, 'next_admin_action', detail?.next_admin_action || '');

    body.appendChild(grid);
    renderAdminClientRequestStatusActions(detail, body);
    renderAdminClientRequestResponseDraftPanel(detail, body);
    renderTimeline(detail, body);
  }

  async function loadAdminClientRequestDetail(requestId) {
    ensureCard();

    const statusTarget = byId('admin-client-request-detail-status');
    const body = byId('admin-client-request-detail-body');
    clear(body);

    if (statusTarget) {
      statusTarget.textContent =
        'Loading detail for request ' + text(requestId) + ' ...';
    }

    try {
      const data = await request(detailPath(requestId));
      renderAdminClientRequestDetail(data?.request || {});
      return data;
    } catch (error) {
      if (statusTarget) {
        statusTarget.textContent =
          'Failed to load request detail: ' +
          (error && error.message ? error.message : String(error));
      }
      return null;
    }
  }

  async function updateAdminClientRequestStatus(requestId, nextStatus) {
    ensureCard();

    const statusTarget = byId('admin-client-request-detail-status');
    if (statusTarget) {
      statusTarget.textContent =
        'Updating request ' + text(requestId) + ' to ' + text(nextStatus) + ' ...';
    }

    try {
      const data = await postJson(statusPath(requestId), {
        status: nextStatus,
        note: 'Updated from Admin request detail panel.',
      });
      renderAdminClientRequestDetail(data?.request || {});
      await loadAdminClientRequests(true);
      return data;
    } catch (error) {
      if (statusTarget) {
        statusTarget.textContent =
          'Failed to update request status: ' +
          (error && error.message ? error.message : String(error));
      }
      return null;
    }
  }
  function renderAdminClientRequests(data) {
    ensureCard();

    const statusTarget = byId('admin-client-requests-status');
    if (statusTarget) {
      statusTarget.textContent = [
        `status: ${text(data?.status || 'unknown')}`,
        `request_count: ${text(data?.request_count ?? 0)}`,
        `latest_count: ${text(data?.latest_count ?? 0)}`,
        text(data?.message || ''),
      ].join('\n');
    }

    renderCounts(data?.status_counts || {});
    renderList(data?.latest_requests || []);
  }

  async function loadAdminClientRequests(force) {
    ensureCard();

    const now = Date.now();
    if (!force && now - lastLoadAt < 1500) {
      return null;
    }
    lastLoadAt = now;

    const statusTarget = byId('admin-client-requests-status');
    if (statusTarget) {
      statusTarget.textContent =
        'Loading admin client requests from ' + ENDPOINT + ' ...';
    }

    try {
      const data = await request(ENDPOINT);
      renderAdminClientRequests(data);
      return data;
    } catch (error) {
      if (statusTarget) {
        statusTarget.textContent =
          'Failed to load admin client requests: ' +
          (error && error.message ? error.message : String(error));
      }
      renderCounts({});
      renderList([]);
      return null;
    }
  }

  function bindAdminClientRequests() {
    ensureCard();

    const refresh = byId('admin-client-requests-refresh-btn');
    if (refresh && !refresh.dataset.boundAdminClientRequests) {
      refresh.dataset.boundAdminClientRequests = '1';
      refresh.addEventListener('click', () => {
        loadAdminClientRequests(true);
      });
    }
  }

  function refreshAdminClientRequestsSoon(force) {
    window.clearTimeout(scheduledRefresh);
    scheduledRefresh = window.setTimeout(() => {
      bindAdminClientRequests();
      loadAdminClientRequests(Boolean(force));
    }, 80);
  }

  function installPageActivationHooks() {
    document.addEventListener(
      'click',
      (event) => {
        const statusButton = event.target.closest('.admin-client-request-status-action');
        if (!statusButton) return;

        event.preventDefault();
        updateAdminClientRequestStatus(
          statusButton.dataset.requestId || '',
          statusButton.dataset.nextStatus || ''
        );
      },
      true
    );
    document.addEventListener(
      'click',
      (event) => {
        const selectButton = event.target.closest('.admin-client-request-select');
        if (!selectButton) return;
        event.preventDefault();
        loadAdminClientRequestDetail(selectButton.dataset.requestId || '');
      },
      true
    );
    document.addEventListener(
      'click',
      (event) => {
        const button = event.target.closest('[data-admin-page], .nav-btn');
        if (!button) return;

        const targetPage = button.dataset?.adminPage || '';
        const label = String(button.textContent || '').toLowerCase();
        if (targetPage === 'clients' || label.includes('clients')) {
          refreshAdminClientRequestsSoon(true);
        }
      },
      true
    );

    window.addEventListener('hashchange', () => {
      if (window.location.hash === '#clients') {
        refreshAdminClientRequestsSoon(true);
      }
    });

    const observer = new MutationObserver(() => {
      const page = byId(PAGE_ID);
      const host = byId(HOST_ID);
      const card = byId(CARD_ID);
      if (page && (!host || !card)) {
        refreshAdminClientRequestsSoon(false);
      }
    });

    if (document.body) {
      observer.observe(document.body, {
        childList: true,
        subtree: true,
      });
    }
  }

  function init() {
    bindAdminClientRequests();
    loadAdminClientRequests(false);
    installPageActivationHooks();

    [150, 500, 1000, 1800].forEach((delay) => {
      window.setTimeout(() => {
        bindAdminClientRequests();
        loadAdminClientRequests(false);
      }, delay);
    });
  }

  window.PMK_ADMIN_CLIENT_REQUESTS = {
    bindAdminClientRequests,
    loadAdminClientRequests,
    loadAdminClientRequestDetail,
    updateAdminClientRequestStatus,
    generateAdminClientRequestResponseDraft,
    saveAdminClientRequestResponseDraft,
    sendAdminClientRequestSupervisorResponse,
    copyAdminClientRequestResponseDraft,
    renderAdminClientRequests,
    renderAdminClientRequestDetail,
    refreshAdminClientRequestsSoon,
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
