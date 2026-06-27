PAGES.governance = (() => {
  const POLICIES_DATA = [
    { id: 'balanced', name: 'BalancedPolicy', desc: 'Default policy — balanced evaluation across all CGT dimensions.', active: true },
    { id: 'conservative', name: 'ConservativePolicy', desc: 'Prioritizes stability and low risk over innovation.', active: false },
    { id: 'fast', name: 'FastPolicy', desc: 'Optimizes for speed and throughput, may accept higher risk.', active: false },
    { id: 'restore', name: 'RestorePolicy', desc: 'Aggressive repair and rehabilitation for failing agents.', active: false },
  ];

  async function refresh() {
    try {
      const st = await GOVERNANCE_ADAPTER.status();
      const policies = st.active_policies || [];
      POLICIES_DATA.forEach(p => {
        p.active = policies.includes(p.id) || policies.includes(p.name);
      });
    } catch (_) {}
    renderPolicies();
    renderSafetyGrid();
  }

  function renderPolicies() {
    const list = document.getElementById('pol-list');
    const detail = document.getElementById('pol-detail');
    if (!list) return;
    list.innerHTML = '';
    POLICIES_DATA.forEach(p => {
      const el = document.createElement('div');
      el.className = 'pol-item' + (p.active ? ' selected' : '');
      el.innerHTML = '<span class="font-data" style="font-size:11px;color:' + (p.active ? 'var(--amber)' : 'var(--soft)') + '">' + p.name + '</span><span class="status-dot"><span class="dot ' + (p.active ? 'ok' : 'idle') + '"></span>' + (p.active ? 'Active' : 'Standby') + '</span>';
      el.addEventListener('click', () => {
        if (detail) {
          detail.style.display = 'block';
          detail.innerHTML = '<div class="card flat"><div class="font-data" style="font-size:11px;color:var(--soft)">' + p.desc + '</div><div class="flex-between" style="margin-top:6px"><span class="font-data text-ghost">Status</span><span class="status-dot"><span class="dot ' + (p.active ? 'ok' : 'idle') + '"></span>' + (p.active ? 'Active' : 'Standby') + '</span></div></div>';
        }
      });
      list.appendChild(el);
    });
  }

  function renderSafetyGrid() {
    const grid = document.getElementById('safety-grid');
    if (!grid) return;
    const items = [
      { label: 'Drift Detection', ok: true },
      { label: 'Boundary Compliance', ok: true },
      { label: 'Rate Limiting', ok: true },
      { label: 'Anomaly Detection', ok: true },
    ];
    grid.innerHTML = items.map(item =>
      '<div class="safety-item"><span class="safety-dot" style="background:' + (item.ok ? 'var(--ok)' : 'var(--error)') + ';box-shadow:0 0 6px ' + (item.ok ? 'var(--ok)' : 'var(--error)') + '"></span><div><div class="font-data" style="font-size:11px;color:var(--soft)">' + item.label + '</div><div class="font-data text-muted" style="font-size:9px">' + (item.ok ? 'Compliant' : 'Violation') + '</div></div></div>'
    ).join('');
  }

  const DECISIONS = [
    { ts: '10:23:45', action: 'PASS', agent: 'agent-alpha', reason: 'Fate vector stable' },
    { ts: '10:22:10', action: 'REPAIR', agent: 'agent-beta', reason: 'Transient rank detected' },
    { ts: '10:20:33', action: 'PASS', agent: 'agent-gamma', reason: 'All thresholds met' },
  ];
  function renderDecisions() {
    const log = document.getElementById('dec-log');
    if (!log) return;
    log.innerHTML = DECISIONS.map(d =>
      '<div class="dec-item" style="margin-bottom:4px"><div class="flex-between"><span class="font-mono text-muted" style="font-size:9px">' + d.ts + '</span><span class="tag" style="font-size:9px;background:' + (d.action === 'PASS' ? 'var(--ok)' : 'var(--warn)') + '20;color:' + (d.action === 'PASS' ? 'var(--ok)' : 'var(--warn)') + '">' + d.action + '</span></div><div class="font-data" style="font-size:10px;color:var(--soft);margin-top:2px">' + d.agent + ' — ' + d.reason + '</div></div>'
    ).join('');
  }

  function init() {
    renderDecisions();
    refresh();
  }

  if (document.readyState !== 'loading') init(); else document.addEventListener('DOMContentLoaded', init);
  return { refresh };
})();
