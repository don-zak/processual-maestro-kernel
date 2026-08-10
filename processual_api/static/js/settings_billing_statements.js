(() => {
  'use strict';

  const state = { loading: false, error: '', statements: [], selected: null };
  const ROOT_ID = 'settings-billing-statements-root';

  function esc(value) {
    return String(value == null ? '' : value).replace(/[&<>"']/g, (char) => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
    })[char]);
  }

  function num(value) {
    const parsed = Number(value || 0);
    return Number.isFinite(parsed) ? parsed.toLocaleString() : '0';
  }

  function currentPeriod() {
    const now = new Date();
    return `${now.getUTCFullYear()}-${String(now.getUTCMonth() + 1).padStart(2, '0')}`;
  }

  function injectStyles() {
    if (document.getElementById('settings-billing-statements-style')) return;
    const style = document.createElement('style');
    style.id = 'settings-billing-statements-style';
    style.textContent = `
      .mbs-shell{margin-top:var(--s-4);display:grid;gap:var(--s-3)}
      .mbs-hero{border:1px solid rgba(245,166,35,.22);background:linear-gradient(135deg,rgba(245,166,35,.08),rgba(147,197,253,.035));padding:var(--s-4);border-radius:14px}
      .mbs-eyebrow{font:700 10px 'Space Mono',monospace;letter-spacing:.14em;text-transform:uppercase;color:var(--amber)}
      .mbs-hero h2{margin:8px 0 6px;font-size:22px}.mbs-hero p{margin:0;max-width:760px;color:var(--text-muted);line-height:1.6}
      .mbs-kpis{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:var(--s-2);margin-top:var(--s-3)}
      .mbs-kpi{padding:14px;border:1px solid var(--border);border-radius:12px;background:rgba(255,255,255,.018)}
      .mbs-kpi span{display:block;color:var(--text-muted);font-size:10px;text-transform:uppercase;letter-spacing:.08em}.mbs-kpi strong{display:block;margin-top:6px;font:700 22px 'DM Mono',monospace}
      .mbs-grid{display:grid;grid-template-columns:minmax(0,.85fr) minmax(0,1.4fr);gap:var(--s-3)}
      .mbs-card{border:1px solid var(--border);border-radius:14px;padding:var(--s-3);background:var(--surface-1,rgba(255,255,255,.02))}
      .mbs-head{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;margin-bottom:14px}.mbs-head h3{margin:0;font-size:15px}.mbs-head small{color:var(--text-muted)}
      .mbs-actions{display:flex;gap:8px;flex-wrap:wrap}.mbs-btn{border:1px solid var(--border);border-radius:9px;padding:8px 11px;background:transparent;color:inherit;cursor:pointer;font:600 11px 'Space Mono',monospace}.mbs-btn.primary{border-color:rgba(245,166,35,.45);background:rgba(245,166,35,.1);color:var(--amber)}.mbs-btn:focus-visible{outline:2px solid var(--amber);outline-offset:2px}
      .mbs-history{display:grid;gap:8px}.mbs-row{display:grid;grid-template-columns:1fr auto;gap:10px;padding:11px;border:1px solid var(--border);border-radius:10px;cursor:pointer}.mbs-row:hover{border-color:rgba(245,166,35,.35)}.mbs-row strong{display:block}.mbs-meta{font:400 10px 'DM Mono',monospace;color:var(--text-muted);margin-top:4px}.mbs-badge{display:inline-flex;align-items:center;gap:5px;font:700 9px 'Space Mono',monospace;text-transform:uppercase;letter-spacing:.06em}.mbs-badge.good{color:var(--ok)}
      .mbs-balance{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin:12px 0}.mbs-balance div{padding:10px;border:1px solid var(--border);border-radius:9px}.mbs-balance span{display:block;color:var(--text-muted);font-size:9px;text-transform:uppercase}.mbs-balance strong{display:block;margin-top:4px;font:600 14px 'DM Mono',monospace}
      .mbs-table{width:100%;border-collapse:collapse;font-size:11px}.mbs-table th,.mbs-table td{text-align:left;padding:8px 6px;border-bottom:1px solid var(--border)}.mbs-table th{color:var(--text-muted);font-size:9px;text-transform:uppercase;letter-spacing:.06em}.mbs-table td:last-child,.mbs-table th:last-child{text-align:right}
      .mbs-sha{display:flex;align-items:center;gap:8px;margin-top:14px;padding:10px;border:1px solid var(--border);border-radius:9px}.mbs-sha code{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:10px;flex:1}.mbs-empty,.mbs-error{padding:16px;border:1px dashed var(--border);border-radius:10px;color:var(--text-muted)}.mbs-error{color:var(--error)}
      @media(max-width:900px){.mbs-grid{grid-template-columns:1fr}.mbs-kpis,.mbs-balance{grid-template-columns:1fr}}
    `;
    document.head.appendChild(style);
  }

  function mount() {
    if (document.getElementById(ROOT_ID)) return document.getElementById(ROOT_ID);
    const usageCard = document.getElementById('set-usage-summary-card');
    const page = document.getElementById('page-settings');
    if (!page) return null;
    const root = document.createElement('div');
    root.id = ROOT_ID;
    root.setAttribute('aria-live', 'polite');
    if (usageCard && usageCard.parentNode) usageCard.parentNode.insertBefore(root, usageCard.nextSibling);
    else (page.firstElementChild || page).appendChild(root);
    injectStyles();
    return root;
  }

  function summaryCard(statement) {
    return `<div class="mbs-row" tabindex="0" role="button" data-mbs-ref="${esc(statement.statement_ref)}" aria-label="View billing statement ${esc(statement.period)}">
      <div><strong>${esc(statement.period)} · ${esc(statement.plan_id)}</strong><div class="mbs-meta">${num(statement.consumed_units)} MU consumed · ${num(statement.remaining_units)} MU remaining${Number(statement.additional_package_count || 0) ? ` · ${num(statement.additional_package_count)} add-on package(s)` : ''}</div></div>
      <div><span class="mbs-badge good">● Verified</span><div class="mbs-meta">${esc(String(statement.statement_sha256 || '').slice(0, 12))}…</div></div>
    </div>`;
  }

  function usageRows(statement) {
    const items = Array.isArray(statement.usage_line_items) ? statement.usage_line_items : [];
    if (!items.length) return '<div class="mbs-empty">No billable Maestro Unit usage in this period.</div>';
    return `<table class="mbs-table"><thead><tr><th>Usage category</th><th>Operations</th><th>Share</th><th>Maestro Units</th></tr></thead><tbody>${items.map((item) => `<tr><td>${esc(item.label)}</td><td>${num(item.request_count)}</td><td>${esc(item.usage_percent)}%</td><td>${num(item.maestro_units)} MU</td></tr>`).join('')}</tbody></table>`;
  }

  function packageRows(statement) {
    const packages = Array.isArray(statement.additional_packages) ? statement.additional_packages : [];
    if (!packages.length) return '<div class="mbs-empty">No additional Maestro Unit packages were granted in this billing period.</div>';
    return `<table class="mbs-table"><thead><tr><th>Additional package</th><th>Settlement</th><th>Granted</th><th>Units</th></tr></thead><tbody>${packages.map((item) => `<tr><td>${num(item.bundle_count)} × ${num(item.bundle_units)} MU<div class="mbs-meta">${esc(item.channel)} · ${esc(String(item.purchase_ref || '').slice(0, 12))}…</div></td><td>${esc(item.settlement_amount)} ${esc(item.settlement_currency)}</td><td>${esc(String(item.granted_at || '').slice(0, 10))}</td><td>${num(item.units_added)} MU</td></tr>`).join('')}</tbody></table>`;
  }

  function detail(statement) {
    if (!statement) return '<div class="mbs-empty">Choose a billing period to review the full reconciliation and downloadable statement.</div>';
    const balance = statement.balance || {};
    return `<div class="mbs-head"><div><h3>${esc(statement.billing_period?.period || '')} statement</h3><small>${esc(statement.statement_ref)}</small></div><div class="mbs-actions"><button class="mbs-btn" data-mbs-copy>Copy SHA-256</button><button class="mbs-btn primary" data-mbs-pdf>Download PDF</button></div></div>
      <div class="mbs-balance"><div><span>Plan + rollover + add-ons</span><strong>${num(balance.available_units)} MU</strong></div><div><span>Consumed</span><strong>${num(balance.consumed_units)} MU</strong></div><div><span>Closing balance</span><strong>${num(balance.remaining_units)} MU</strong></div></div>
      <h4>Usage breakdown</h4>${usageRows(statement)}<h4 style="margin-top:18px">Additional packages</h4>${packageRows(statement)}
      <div class="mbs-sha"><span class="mbs-badge good">● SHA-256 verified</span><code title="${esc(statement.statement_sha256)}">${esc(statement.statement_sha256)}</code></div>`;
  }

  function render() {
    const root = mount();
    if (!root) return;
    const latest = state.statements[0] || {};
    root.innerHTML = `<section class="mbs-shell" aria-labelledby="mbs-title">
      <div class="mbs-hero"><div class="mbs-eyebrow">Billing & usage</div><h2 id="mbs-title">Understand every Maestro Unit</h2><p>Review plan allowance, rollover, purchased add-on packages, billable usage, closing balance, and the SHA-256 integrity fingerprint from one reconciled statement.</p>
        <div class="mbs-kpis"><div class="mbs-kpi"><span>Latest consumed</span><strong>${latest.statement_ref ? `${num(latest.consumed_units)} MU` : '—'}</strong></div><div class="mbs-kpi"><span>Latest balance</span><strong>${latest.statement_ref ? `${num(latest.remaining_units)} MU` : '—'}</strong></div><div class="mbs-kpi"><span>Add-on packages</span><strong>${latest.statement_ref ? num(latest.additional_package_count) : '—'}</strong></div></div>
      </div>
      ${state.error ? `<div class="mbs-error" role="alert">${esc(state.error)}</div>` : ''}
      <div class="mbs-grid"><section class="mbs-card"><div class="mbs-head"><div><h3>Statement history</h3><small>Immutable, verified billing snapshots</small></div><div class="mbs-actions"><button class="mbs-btn" data-mbs-refresh>Refresh</button><button class="mbs-btn primary" data-mbs-issue>Issue ${esc(currentPeriod())}</button></div></div>${state.loading ? '<div class="mbs-empty">Loading billing statements…</div>' : (state.statements.length ? `<div class="mbs-history">${state.statements.map(summaryCard).join('')}</div>` : '<div class="mbs-empty">No billing statements have been issued yet. Issue the current period once an authoritative quota cycle is available.</div>')}</section>
      <section class="mbs-card" data-mbs-detail>${detail(state.selected)}</section></div>
    </section>`;
    bind();
  }

  async function load() {
    state.loading = true; state.error = ''; render();
    try {
      const payload = await CLIENT.get('/billing/statements');
      state.statements = Array.isArray(payload.statements) ? payload.statements : [];
      if (state.selected && !state.statements.some((item) => item.statement_ref === state.selected.statement_ref)) state.selected = null;
    } catch (error) {
      state.error = error?.detail || error?.message || 'Billing statements are unavailable.';
    } finally { state.loading = false; render(); }
  }

  async function select(ref) {
    try {
      const payload = await CLIENT.get(`/billing/statements/${encodeURIComponent(ref)}`);
      state.selected = payload.statement || null; state.error = ''; render();
    } catch (error) { state.error = error?.detail || error?.message || 'Unable to verify this billing statement.'; render(); }
  }

  async function issue() {
    state.error = '';
    try {
      const payload = await CLIENT.post(`/billing/statements/${currentPeriod()}`, {});
      state.selected = payload.statement || null;
      await load();
      if (state.selected) await select(state.selected.statement_ref);
    } catch (error) { state.error = error?.detail || error?.message || 'The current statement cannot be issued until authoritative billing inputs reconcile.'; render(); }
  }

  function downloadPdf() {
    if (!state.selected?.statement_ref) return;
    window.location.assign(`/billing/statements/${encodeURIComponent(state.selected.statement_ref)}/pdf`);
  }

  async function copySha() {
    if (!state.selected?.statement_sha256) return;
    await navigator.clipboard.writeText(state.selected.statement_sha256);
    if (window.APP?.showToast) APP.showToast('Statement SHA-256 copied', 'success');
  }

  function bind() {
    const root = document.getElementById(ROOT_ID); if (!root) return;
    root.querySelector('[data-mbs-refresh]')?.addEventListener('click', load);
    root.querySelector('[data-mbs-issue]')?.addEventListener('click', issue);
    root.querySelector('[data-mbs-pdf]')?.addEventListener('click', downloadPdf);
    root.querySelector('[data-mbs-copy]')?.addEventListener('click', copySha);
    root.querySelectorAll('[data-mbs-ref]').forEach((row) => {
      const open = () => select(row.dataset.mbsRef);
      row.addEventListener('click', open);
      row.addEventListener('keydown', (event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); open(); } });
    });
  }

  function init() { mount(); load(); }
  window.PMK_SETTINGS_BILLING_STATEMENTS = { init, refresh: load };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, { once: true }); else init();
})();
