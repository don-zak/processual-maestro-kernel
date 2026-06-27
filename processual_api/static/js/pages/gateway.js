PAGES.gateway = (() => {
  let gwChart = null;
  let gwDonutChart = null;

  async function refresh() {
    try {
      const [agentsData, dashData] = await Promise.all([
        GATEWAY_ADAPTER.listAgents(),
        GATEWAY_ADAPTER.dashboard().catch(() => null)
      ]);
      const agents = agentsData.agents || [];
      // Sync to shared state
      APP.gwAgents.length = 0;
      agents.forEach(a => APP.gwAgents.push(a));

      renderSummary(agents);
      populateEvalSelect(agents);
      renderTable(agents);
      renderDonut(agents);
      CHARTS.drawStateDiagram('gw-state-diagram', agents.map(a => a.state));
      updateGauge(agents);
      renderTrendChart(agents);
    } catch (e) {
      APP.showToast('Gateway load failed: ' + e.message, 'error');
    }
  }

  function renderSummary(agents) {
    const total = agents.length;
    const active = agents.filter(a => a.state === 'active').length;
    const atRisk = agents.filter(a => (a.consecutive_failures || 0) >= 3).length;
    const avgRew = total ? agents.reduce((s, a) => s + (a.avg_reward || 0), 0) / total : 0;
    document.getElementById('gw-total').textContent = total;
    document.getElementById('gw-active').textContent = active;
    document.getElementById('gw-at-risk').textContent = atRisk;
    document.getElementById('gw-avg-reward').textContent = avgRew.toFixed(2);
  }

  function populateEvalSelect(agents) {
    const sel = document.getElementById('gw-eval-agent');
    if (!sel) return;
    sel.innerHTML = '';
    agents.forEach(a => {
      const opt = document.createElement('option');
      opt.value = a.agent_id;
      opt.textContent = a.agent_id + ' (' + a.state + ')';
      sel.appendChild(opt);
    });
  }

  function renderTable(agents) {
    const search = (document.getElementById('gw-search')?.value || '').toLowerCase();
    const stateFilter = document.getElementById('gw-filter-state')?.value || '';
    const rankFilter = document.getElementById('gw-filter-rank')?.value || '';

    let filtered = agents.filter(a => {
      if (search && !a.agent_id.toLowerCase().includes(search) && !(a.name || '').toLowerCase().includes(search)) return false;
      if (stateFilter && a.state !== stateFilter) return false;
      if (rankFilter) {
        const evals = a.evaluations || [];
        const lastRank = evals.length ? evals[evals.length - 1].rank : '';
        if (lastRank !== rankFilter) return false;
      }
      return true;
    });

    document.getElementById('gw-agent-count').textContent = filtered.length + ' agents registered';
    const table = document.getElementById('gw-table');
    if (!table) return;
    table.innerHTML = '';
    const hdr = document.createElement('div');
    hdr.className = 'agent-hdr';
    hdr.innerHTML = '<span>Agent</span><span>Role</span><span>State</span><span>Reward</span><span>Trend</span><span>Failures</span>';
    table.appendChild(hdr);

    filtered.forEach((a, i) => {
      const r = document.createElement('div');
      r.className = 'agent-row';
      r.style.cursor = 'pointer';
      r.style.animation = 'slide-in-left 0.' + (2 + i) + 's ease both';
      r.addEventListener('click', () => openDetail(a.agent_id));
      const trendSym = a.trend === 'up' ? '↑' : a.trend === 'down' ? '↓' : '→';
      r.innerHTML =
        '<span class="font-mono" style="font-size:11px;color:var(--amber)">' + a.agent_id + '</span>' +
        '<span class="font-data text-ghost" style="font-size:10px">' + (a.role || '—') + '</span>' +
        '<span><span class="gw-state-badge ' + a.state + '" style="font-size:9px">' + a.state + '</span></span>' +
        '<span class="font-mono" style="font-size:12px;color:' + ((a.avg_reward || 0) > 0.5 ? 'var(--ok)' : (a.avg_reward || 0) > 0 ? 'var(--amber)' : 'var(--error)') + '">' + (a.avg_reward || 0).toFixed(2) + '</span>' +
        '<span class="font-mono" style="font-size:11px;color:' + (a.trend === 'up' ? 'var(--ok)' : a.trend === 'down' ? 'var(--error)' : 'var(--muted)') + '">' + trendSym + '</span>' +
        '<span class="font-mono" style="font-size:11px;color:' + ((a.consecutive_failures || 0) > 0 ? 'var(--error)' : 'var(--muted)') + '">' + (a.consecutive_failures || 0) + '</span>';
      table.appendChild(r);
    });
  }

  function renderDonut(agents) {
    const canvas = document.getElementById('gw-donut');
    if (!canvas) return;
    const counts = {};
    agents.forEach(a => { counts[a.state] = (counts[a.state] || 0) + 1; });
    const labels = Object.keys(counts);
    const data = Object.values(counts);
    const colors = { active: '#22d3a0', pending: '#fbbf24', frozen: '#60a5fa', escalated: '#fb923c', rehabilitating: '#a78bfa', deactivated: '#f87171' };

    if (gwDonutChart) { gwDonutChart.destroy(); gwDonutChart = null; }
    if (labels.length) {
      gwDonutChart = CHARTS.createChart('gw-donut', 'doughnut', labels,
        [{ data, backgroundColor: labels.map(l => colors[l] || '#3d5070'), borderWidth: 0 }],
        { cutout: '65%', plugins: { legend: { display: true, position: 'bottom', labels: { color: '#8aa3c8', font: { size: 9 }, padding: 8 } } } }
      );
    }
  }

  function updateGauge(agents) {
    const total = agents.length;
    const avg = total ? agents.reduce((s, a) => s + (a.avg_reward || 0), 0) / total : 0;
    CHARTS.drawGauge('gw-gauge', avg, -2, 2);
  }

  function renderTrendChart(agents) {
    const canvas = document.getElementById('gw-trend-canvas');
    if (!canvas) return;
    const allEvals = [];
    agents.forEach(a => {
      (a.evaluations || []).forEach(e => {
        allEvals.push({ agent_id: a.agent_id, ts: e.ts, reward: e.reward });
      });
    });
    allEvals.sort((a, b) => new Date(a.ts) - new Date(b.ts));
    const recent = allEvals.slice(-30);
    if (recent.length < 2) {
      const ctx = canvas.getContext('2d');
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      return;
    }
    CHARTS.drawTrendChart('gw-trend-canvas', recent);
  }

  /* ─── Register Agent ─── */
  async function register() {
    const id = document.getElementById('gw-reg-id').value.trim();
    const name = document.getElementById('gw-reg-name').value.trim() || id;
    const role = document.getElementById('gw-reg-role').value;
    const adapter = document.getElementById('gw-reg-adapter').value;
    const resultDiv = document.getElementById('gw-reg-result');
    if (!id) { resultDiv.innerHTML = '<span class="font-data text-warn" style="font-size:11px;color:var(--warn)">Agent ID is required</span>'; return; }

    APP.showLoading('gw-reg-btn', 'Registering...');
    try {
      const res = await GATEWAY_ADAPTER.registerAgent({ agent_id: id, name, role, adapter_name: adapter });
      resultDiv.innerHTML = '<span class="font-data" style="font-size:11px;color:var(--ok)">✓ ' + id + ' registered (' + res.state + ')</span>';
      document.getElementById('gw-reg-id').value = '';
      APP.showToast('Agent ' + id + ' registered', 'success');
      await refresh();
    } catch (e) {
      resultDiv.innerHTML = '<span class="font-data" style="font-size:11px;color:var(--error)">Error: ' + (e.detail || e.message) + '</span>';
      APP.showToast('Registration failed', 'error');
    }
    APP.hideLoading('gw-reg-btn');
  }

  /* ─── Evaluate Agent ─── */
  async function evaluate() {
    const agentId = document.getElementById('gw-eval-agent').value;
    const query = document.getElementById('gw-eval-query').value.trim();
    const response = document.getElementById('gw-eval-response').value.trim();
    const resultDiv = document.getElementById('gw-eval-result');
    if (!agentId || !query || !response) { resultDiv.innerHTML = '<div class="text-muted font-data" style="font-size:11px;padding:var(--s-2)">Please fill all fields</div>'; return; }

    APP.showLoading('gw-eval-btn', 'Evaluating...');
    try {
      const res = await GATEWAY_ADAPTER.evaluate(agentId, query, response, 'en');
      const action = res.action || 'pass';
      const rank = res.rank || 'stable';
      const reward = res.reward || 0;
      const rc = APP.rankColors[rank] || APP.rankColors.stable;
      const actionColor = APP.getGwActionColor(action);

      resultDiv.innerHTML =
        '<div class="card flat" style="margin-top:var(--s-2)">' +
        '<div class="flex-gap" style="margin-bottom:var(--s-3)">' +
        '<span class="rank-badge" style="background:' + rc.bg + ';border:1px solid ' + rc.c + '40;color:' + rc.c + ';padding:3px 10px;font-size:11px"><span class="rdot" style="background:' + rc.c + '"></span>' + rank + '</span>' +
        '<span class="tag" style="background:' + actionColor + '20;color:' + actionColor + ';border:1px solid ' + actionColor + '40;font-size:11px">' + action.toUpperCase() + '</span>' +
        '</div>' +
        '<div class="flex-between"><span class="font-data text-ghost" style="font-size:11px">Gateway Action</span><span class="font-mono" style="font-size:13px;font-weight:700;color:' + actionColor + '">' + action.toUpperCase() + '</span></div>' +
        '<div class="flex-between" style="margin-top:4px"><span class="font-data text-ghost" style="font-size:11px">CGT Reward</span><span class="font-mono" style="font-size:13px;font-weight:700;color:' + (reward > 0 ? 'var(--ok)' : 'var(--error)') + '">' + (reward > 0 ? '+' : '') + reward.toFixed(4) + '</span></div>' +
        '<div class="flex-between" style="margin-top:4px"><span class="font-data text-ghost" style="font-size:11px">Policy</span><span class="font-data text-soft" style="font-size:11px">' + (res.policy_label || '—') + '</span></div>' +
        '<div class="flex-between" style="margin-top:4px"><span class="font-data text-ghost" style="font-size:11px">Agent State</span><span class="gw-state-badge ' + (res.agent_state || 'active') + '">' + (res.agent_state || '—') + '</span></div>' +
        (res.signature ? '<div class="flex-between" style="margin-top:4px"><span class="font-data text-ghost" style="font-size:11px">SHA3-256</span><span class="font-mono text-muted" style="font-size:8px;max-width:200px;overflow:hidden;text-overflow:ellipsis">' + res.signature + '</span></div>' : '') +
        '</div>';
      APP.showToast('Evaluation: ' + action.toUpperCase() + ' — ' + agentId, action === 'block' ? 'error' : action === 'repair' ? 'warn' : 'success');
      await refresh();
    } catch (e) {
      resultDiv.innerHTML = '<div class="text-muted font-data" style="font-size:11px;color:var(--error)">Error: ' + (e.detail || e.message) + '</div>';
    }
    APP.hideLoading('gw-eval-btn');
  }

  /* ─── Agent Detail Panel ─── */
  async function openDetail(agentId) {
    try {
      const a = await GATEWAY_ADAPTER.getAgent(agentId);
      const overlay = document.getElementById('gw-detail-overlay');
      const panel = document.getElementById('gw-agent-detail');
      if (!overlay || !panel) return;
      overlay.classList.add('open');
      panel.classList.add('open');

      const evals = a.evaluations || [];
      const lastEval = evals.length ? evals[evals.length - 1] : null;
      const rc = lastEval ? (APP.rankColors[lastEval.rank] || APP.rankColors.stable) : { c: 'var(--muted)', bg: 'transparent' };

      panel.innerHTML =
        '<div class="flex-between" style="margin-bottom:var(--s-3)"><div><div class="font-mono" style="font-size:14px;color:var(--amber);font-weight:700">' + a.agent_id + '</div><div class="font-data text-ghost" style="font-size:10px">' + (a.role || '—') + ' · ' + (a.adapter || '—') + '</div></div>' +
        '<button class="btn ghost sm" onclick="document.getElementById(\'gw-detail-overlay\').classList.remove(\'open\');document.getElementById(\'gw-agent-detail\').classList.remove(\'open\')">✕</button></div>' +
        '<div class="grid-3" style="margin-bottom:var(--s-3)">' +
        '<div class="card flat" style="padding:var(--s-2)"><span class="font-data text-ghost" style="font-size:9px">State</span><div><span class="gw-state-badge ' + a.state + '">' + a.state + '</span></div></div>' +
        '<div class="card flat" style="padding:var(--s-2)"><span class="font-data text-ghost" style="font-size:9px">Avg Reward</span><div class="font-mono" style="font-size:14px;color:' + ((a.avg_reward || 0) > 0.5 ? 'var(--ok)' : (a.avg_reward || 0) > 0 ? 'var(--amber)' : 'var(--error)') + '">' + (a.avg_reward || 0).toFixed(4) + '</div></div>' +
        '<div class="card flat" style="padding:var(--s-2)"><span class="font-data text-ghost" style="font-size:9px">Failures</span><div class="font-mono" style="font-size:14px;color:' + ((a.consecutive_failures || 0) > 0 ? 'var(--error)' : 'var(--ok)') + '">' + (a.consecutive_failures || 0) + '</div></div></div>' +
        (lastEval ? '<div class="flex-gap" style="margin-bottom:var(--s-3)"><span class="rank-badge" style="background:' + rc.bg + ';border:1px solid ' + rc.c + '40;color:' + rc.c + '">' + lastEval.rank + '</span><span class="font-mono" style="font-size:11px;color:' + (lastEval.reward > 0 ? 'var(--ok)' : 'var(--error)') + '">' + (lastEval.reward > 0 ? '+' : '') + lastEval.reward.toFixed(4) + '</span></div>' : '') +
        '<div style="margin-bottom:var(--s-3)"><span class="font-data text-ghost" style="font-size:10px">Lifecycle Actions</span><div class="flex-gap" style="margin-top:var(--s-1);flex-wrap:wrap">' +
        ['activate','freeze','escalate','rehabilitate','deactivate'].map(act =>
          '<button class="btn ghost sm" style="font-size:10px;padding:3px 10px" onclick="PAGES.gateway.lifecycleAction(\'' + a.agent_id + '\',\'' + act + '\')">' + act.charAt(0).toUpperCase() + act.slice(1) + '</button>'
        ).join('') +
        '</div></div>' +
        '<div><span class="font-data text-ghost" style="font-size:10px">Evaluation History</span>' +
        (evals.length ? '<div style="margin-top:var(--s-1);max-height:150px;overflow-y:auto">' + evals.slice(-10).reverse().map(e =>
          '<div class="flex-between" style="padding:3px 0;border-bottom:1px solid var(--surface-0);font-size:10px"><span class="font-mono text-muted" style="font-size:8px">' + new Date(e.ts).toLocaleTimeString() + '</span><span class="font-mono" style="color:' + (e.reward > 0 ? 'var(--ok)' : 'var(--error)') + '">' + e.reward.toFixed(4) + '</span><span class="rank-badge" style="background:' + (APP.rankColors[e.rank]?.bg || 'transparent') + ';color:' + (APP.rankColors[e.rank]?.c || 'var(--muted)') + ';padding:1px 6px;font-size:8px">' + (e.rank || '—') + '</span></div>'
        ).join('') + '</div>' : '<div class="text-muted font-data" style="font-size:10px;margin-top:4px">No evaluations yet</div>') +
        '</div>';
    } catch (e) {
      APP.showToast('Failed to load agent detail: ' + e.message, 'error');
    }
  }

  /* ─── Lifecycle Action ─── */
  async function lifecycleAction(agentId, action) {
    try {
      const res = await GATEWAY_ADAPTER.agentAction(agentId, action, 'Manual action from console');
      APP.showToast('Agent ' + agentId + ' → ' + (res.new_state || action), 'success');
      await refresh();
      openDetail(agentId);
    } catch (e) {
      APP.showToast('Action failed: ' + (e.detail || e.message), 'error');
    }
  }

  /* ─── Exports ─── */
  function exportCSV() {
    const agents = APP.gwAgents;
    const h = 'agent_id,role,state,avg_reward,trend,failures\n';
    const rows = agents.map(a => [a.agent_id, a.role, a.state, a.avg_reward || 0, a.trend || '', a.consecutive_failures || 0].join(',')).join('\n');
    const blob = new Blob([h + rows], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a2 = document.createElement('a'); a2.href = url; a2.download = 'gateway-agents.csv'; a2.click();
    URL.revokeObjectURL(url);
    APP.showToast('CSV exported', 'success');
  }

  function exportJSON() {
    const blob = new Blob([JSON.stringify(APP.gwAgents, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a2 = document.createElement('a'); a2.href = url; a2.download = 'gateway-agents.json'; a2.click();
    URL.revokeObjectURL(url);
    APP.showToast('JSON exported', 'success');
  }

  /* ─── Init ─── */
  function init() {
    document.getElementById('gw-reg-btn')?.addEventListener('click', register);
    document.getElementById('gw-eval-btn')?.addEventListener('click', evaluate);
    document.getElementById('gw-search')?.addEventListener('input', () => renderTable(APP.gwAgents));
    document.getElementById('gw-filter-state')?.addEventListener('change', () => renderTable(APP.gwAgents));
    document.getElementById('gw-filter-rank')?.addEventListener('change', () => renderTable(APP.gwAgents));
    document.getElementById('gw-pdf-btn')?.addEventListener('click', () => {
      GATEWAY_ADAPTER.pdfReport().then(blob => {
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a'); a.href = url; a.download = 'gateway-report.pdf'; a.click();
        URL.revokeObjectURL(url);
        APP.showToast('PDF downloaded', 'success');
      }).catch(() => APP.showToast('PDF download failed', 'error'));
    });
    document.getElementById('gw-export-csv')?.addEventListener('click', exportCSV);
    document.getElementById('gw-export-json')?.addEventListener('click', exportJSON);
    document.getElementById('gw-detail-overlay')?.addEventListener('click', () => {
      document.getElementById('gw-detail-overlay').classList.remove('open');
      document.getElementById('gw-agent-detail').classList.remove('open');
    });

    // Auto-refresh every 10s (only if page is visible)
    setInterval(() => {
      const gwPage = document.getElementById('page-gateway');
      if (gwPage && gwPage.classList.contains('active')) refresh();
    }, 10000);
  }

  // Auto-init
  if (document.readyState !== 'loading') init(); else document.addEventListener('DOMContentLoaded', init);

  return { refresh, lifecycleAction, openDetail };
})();
