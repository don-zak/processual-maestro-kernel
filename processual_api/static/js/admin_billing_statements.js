(() => {
  'use strict';

  const ROOT_ID = 'admin-billing-statements-root';
  const state = { loading: false, error: '', clientId: '', period: '', statements: [], selected: null };

  function esc(value) {
    return String(value == null ? '' : value).replace(/[&<>"']/g, (char) => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
    })[char]);
  }

  function num(value) {
    const n = Number(value || 0);
    return Number.isFinite(n) ? n.toLocaleString() : '0';
  }

  function headers() {
    const auth = window.PMK_ADMIN_AUTH;
    return auth && typeof auth.headers === 'function' ? auth.headers({}) : {};
  }

  function defaultPeriod() {
    const now = new Date();
    return `${now.getUTCFullYear()}-${String(now.getUTCMonth() + 1).padStart(2, '0')}`;
  }

  function injectStyles() {
    if (document.getElementById('admin-billing-statements-style')) return;
    const style = document.createElement('style');
    style.id = 'admin-billing-statements-style';
    style.textContent = `
      .abs-shell{margin-top:18px}.abs-card{border:1px solid var(--admin-border,#283348);border-radius:14px;background:var(--admin-card,#111827);padding:18px}.abs-head{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;flex-wrap:wrap}.abs-head h2{margin:2px 0 5px}.abs-sub{color:var(--admin-muted,#94a3b8);font-size:12px;line-height:1.55}.abs-form{display:grid;grid-template-columns:minmax(220px,1fr) 150px auto auto;gap:8px;margin:16px 0}.abs-input{min-height:38px;border:1px solid var(--admin-border,#334155);border-radius:8px;background:transparent;color:inherit;padding:0 10px}.abs-btn{min-height:38px;border:1px solid var(--admin-border,#334155);border-radius:8px;background:transparent;color:inherit;padding:0 12px;cursor:pointer}.abs-btn.primary{border-color:#f59e0b;color:#f59e0b;background:rgba(245,158,11,.08)}.abs-btn:focus-visible,.abs-input:focus-visible{outline:2px solid #f59e0b;outline-offset:2px}.abs-grid{display:grid;grid-template-columns:minmax(0,.8fr) minmax(0,1.3fr);gap:14px}.abs-panel{border:1px solid var(--admin-border,#283348);border-radius:11px;padding:13px}.abs-list{display:grid;gap:8px}.abs-row{display:grid;grid-template-columns:1fr auto;gap:10px;padding:10px;border:1px solid var(--admin-border,#283348);border-radius:9px;cursor:pointer}.abs-row:hover{border-color:rgba(245,158,11,.45)}.abs-meta{color:var(--admin-muted,#94a3b8);font-size:10px;margin-top:4px}.abs-good{color:#22c55e;font-size:10px;font-weight:700}.abs-kpis{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin:12px 0}.abs-kpi{border:1px solid var(--admin-border,#283348);border-radius:8px;padding:9px}.abs-kpi span{display:block;color:var(--admin-muted,#94a3b8);font-size:9px;text-transform:uppercase}.abs-kpi strong{display:block;margin-top:5px}.abs-table{width:100%;border-collapse:collapse;font-size:11px}.abs-table th,.abs-table td{padding:7px 5px;border-bottom:1px solid var(--admin-border,#283348);text-align:left}.abs-table td:last-child,.abs-table th:last-child{text-align:right}.abs-sha{word-break:break-all;font-family:monospace;font-size:10px;color:var(--admin-muted,#94a3b8)}.abs-empty,.abs-error{padding:12px;border:1px dashed var(--admin-border,#283348);border-radius:8px;color:var(--admin-muted,#94a3b8)}.abs-error{color:#f87171}@media(max-width:980px){.abs-grid,.abs-form{grid-template-columns:1fr}.abs-kpis{grid-template-columns:1fr}}
    `;
    document.head.appendChild(style);
  }

  function mount() {
    if (document.getElementById(ROOT_ID)) return document.getElementById(ROOT_ID);
    const analytics = document.getElementById('admin-subscription-analytics-host');
    const parent = analytics?.parentNode || document.querySelector('main') || document.body;
    const root = document.createElement('div');
    root.id = ROOT_ID;
    root.setAttribute('aria-live', 'polite');
    if (analytics?.nextSibling) parent.insertBefore(root, analytics.nextSibling); else parent.appendChild(root);
    injectStyles();
    return root;
  }

  async function request(path, options) {
    const response = await fetch(path, { credentials: 'include', headers: { ...headers(), 'Content-Type': 'application/json' }, ...(options || {}) });
    let payload = null;
    try { payload = await response.json(); } catch (_) { payload = null; }
    if (!response.ok) throw new Error(payload?.detail || `Request failed with status ${response.status}`);
    return payload || {};
  }

  function listRows() {
    if (!state.statements.length) return '<div class="abs-empty">No verified billing statements match this filter.</div>';
    return `<div class="abs-list">${state.statements.map((item) => `<div class="abs-row" tabindex="0" role="button" data-abs-ref="${esc(item.statement_ref)}"><div><strong>${esc(item.period)} · ${esc(item.plan_id)}</strong><div class="abs-meta">${esc(item.client_id)} · ${num(item.consumed_units)} MU consumed · ${num(item.additional_package_count)} add-on package(s)</div></div><div><span class="abs-good">● VERIFIED</span><div class="abs-meta">${esc(String(item.statement_sha256 || '').slice(0,12))}…</div></div></div>`).join('')}</div>`;
  }

  function packageRows(statement) {
    const items = Array.isArray(statement?.additional_packages) ? statement.additional_packages : [];
    if (!items.length) return '<div class="abs-empty">No granted add-on packages in this statement.</div>';
    return `<table class="abs-table"><thead><tr><th>Purchase</th><th>Settlement</th><th>Units</th></tr></thead><tbody>${items.map((item) => `<tr><td>${esc(String(item.purchase_ref || '').slice(0,12))}…<div class="abs-meta">${num(item.bundle_count)} × ${num(item.bundle_units)} MU · ${esc(item.channel)}</div></td><td>${esc(item.settlement_amount)} ${esc(item.settlement_currency)}</td><td>${num(item.units_added)} MU</td></tr>`).join('')}</tbody></table>`;
  }

  function detail() {
    const s = state.selected;
    if (!s) return '<div class="abs-empty">Select a statement to inspect the complete reconciled snapshot.</div>';
    const b = s.balance || {};
    return `<div class="abs-head"><div><strong>${esc(s.statement_ref)}</strong><div class="abs-meta">${esc(s.client_id)} · ${esc(s.billing_period?.period)} · ${esc(s.plan?.plan_id)}</div></div><div><button class="abs-btn" data-abs-copy>Copy SHA-256</button> <button class="abs-btn primary" data-abs-pdf>Download PDF</button></div></div><div class="abs-kpis"><div class="abs-kpi"><span>Available</span><strong>${num(b.available_units)} MU</strong></div><div class="abs-kpi"><span>Consumed</span><strong>${num(b.consumed_units)} MU</strong></div><div class="abs-kpi"><span>Closing balance</span><strong>${num(b.remaining_units)} MU</strong></div></div><h3>Additional packages</h3>${packageRows(s)}<h3>Integrity</h3><div class="abs-meta">Usage reconciliation: ${esc(String(s.reconciliation?.reconciled))} · Add-on reconciliation: ${esc(String(s.reconciliation?.top_ups_reconciled))}</div><p class="abs-sha">${esc(s.statement_sha256)}</p>`;
  }

  function render() {
    const root = mount(); if (!root) return;
    root.innerHTML = `<section class="abs-shell"><div class="abs-card"><div class="abs-head"><div><p class="admin-eyebrow">Billing authority</p><h2>Customer Billing Statements</h2><p class="abs-sub">Issue, verify, search, and export immutable Maestro Unit statements. Every statement reconciles plan allowance, rollover, granted add-on packages, billable usage, closing balance, and SHA-256 integrity.</p></div></div><div class="abs-form"><input class="abs-input" id="abs-client" aria-label="Client UUID" placeholder="Client UUID" value="${esc(state.clientId)}"><input class="abs-input" id="abs-period" aria-label="Billing period" placeholder="YYYY-MM" value="${esc(state.period || defaultPeriod())}"><button class="abs-btn" data-abs-search>Search</button><button class="abs-btn primary" data-abs-issue>Issue statement</button></div>${state.error ? `<div class="abs-error" role="alert">${esc(state.error)}</div>` : ''}<div class="abs-grid"><div class="abs-panel"><h3>Statement history</h3>${state.loading ? '<div class="abs-empty">Loading verified statements…</div>' : listRows()}</div><div class="abs-panel">${detail()}</div></div></div></section>`;
    bind();
  }

  async function load() {
    state.loading = true; state.error = ''; render();
    try {
      const query = state.clientId ? `?client_id=${encodeURIComponent(state.clientId)}` : '';
      const payload = await request(`/billing/admin/statements${query}`);
      state.statements = Array.isArray(payload.statements) ? payload.statements : [];
    } catch (error) { state.error = error.message || 'Billing statements unavailable.'; }
    finally { state.loading = false; render(); }
  }

  async function select(ref) {
    try { const payload = await request(`/billing/admin/statements/${encodeURIComponent(ref)}`); state.selected = payload.statement || null; state.error = ''; render(); }
    catch (error) { state.error = error.message || 'Unable to verify statement.'; render(); }
  }

  async function issue() {
    const client = document.getElementById('abs-client')?.value.trim() || '';
    const period = document.getElementById('abs-period')?.value.trim() || defaultPeriod();
    state.clientId = client; state.period = period;
    if (!client) { state.error = 'Enter the client UUID before issuing a statement.'; render(); return; }
    try {
      const payload = await request(`/billing/admin/statements/${encodeURIComponent(client)}/${encodeURIComponent(period)}`, { method: 'POST', body: '{}' });
      state.selected = payload.statement || null; await load(); if (state.selected) await select(state.selected.statement_ref);
    } catch (error) { state.error = error.message || 'Statement issuance failed because authoritative billing inputs did not reconcile.'; render(); }
  }

  function bind() {
    const root = document.getElementById(ROOT_ID); if (!root) return;
    root.querySelector('[data-abs-search]')?.addEventListener('click', () => { state.clientId = document.getElementById('abs-client')?.value.trim() || ''; state.period = document.getElementById('abs-period')?.value.trim() || ''; load(); });
    root.querySelector('[data-abs-issue]')?.addEventListener('click', issue);
    root.querySelector('[data-abs-pdf]')?.addEventListener('click', () => { if (state.selected?.statement_ref) window.location.assign(`/billing/admin/statements/${encodeURIComponent(state.selected.statement_ref)}/pdf`); });
    root.querySelector('[data-abs-copy]')?.addEventListener('click', async () => { if (state.selected?.statement_sha256) await navigator.clipboard.writeText(state.selected.statement_sha256); });
    root.querySelectorAll('[data-abs-ref]').forEach((row) => { const open = () => select(row.dataset.absRef); row.addEventListener('click', open); row.addEventListener('keydown', (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); open(); } }); });
  }

  function init() { mount(); load(); }
  window.PMK_ADMIN_BILLING_STATEMENTS = { init, refresh: load };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, { once: true }); else init();
})();
