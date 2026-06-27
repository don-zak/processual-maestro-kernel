PAGES.overview = (() => {
  let ovChart = null;
  let ovTick = 0;

  async function refresh() {
    try {
      const [live, govStatus, metrics] = await Promise.all([
        HEALTH_ADAPTER.live().catch(() => ({ status: 'unknown', service: 'maestro', version: '?' })),
        GOVERNANCE_ADAPTER.status().catch(() => ({ mode: 'unknown', active_policies: [], drift_monitoring: false, certification_level: 'unknown' })),
        fetch('/cgt/govern/metrics').then(r => r.json()).catch(() => null)
      ]);

      document.getElementById('gov-mode').textContent = (govStatus.mode || '').replace(/_/g, ' ');
      document.getElementById('gov-mode2').textContent = (govStatus.mode || '').replace(/_/g, ' ');
      document.getElementById('gov-cert').textContent = (govStatus.certification_level || '').replace(/_/g, ' ');
      document.getElementById('gov-drift').textContent = govStatus.drift_monitoring ? 'Active' : 'Off';
      document.getElementById('gov-drift').style.color = govStatus.drift_monitoring ? 'var(--ok)' : 'var(--error)';
      document.getElementById('gov-pol-count').textContent = (govStatus.active_policies || []).length;
      document.getElementById('gov-policies').innerHTML = (govStatus.active_policies || []).map(p =>
        '<span class="tag" style="background:rgba(138,163,200,0.094);color:var(--soft);border:1px solid rgba(138,163,200,0.188)">' + p + '</span>'
      ).join('');

      // Real metrics
      if (metrics) {
        document.getElementById('ov-total-evals').textContent = metrics.total_evaluations || 0;
        document.getElementById('ov-avg-reward-all').textContent = metrics.avg_reward ? metrics.avg_reward.toFixed(4) : '—';
        document.getElementById('ov-active-agents').textContent = metrics.active_agents || 0;
        document.getElementById('ov-total-agents').textContent = metrics.total_agents || 0;
        document.getElementById('ov-agent-avg-reward').textContent = metrics.agent_avg_reward ? metrics.agent_avg_reward.toFixed(4) : '—';
        document.getElementById('ov-policy-actions').textContent = metrics.policy_action_count || 0;

        // Rank distribution
        const dist = metrics.rank_distribution || {};
        const distHtml = Object.entries(dist).map(([k, v]) =>
          '<span class="tag" style="background:rgba(138,163,200,0.094);color:var(--soft);border:1px solid rgba(138,163,200,0.188)">' + k + ': ' + v + '</span>'
        ).join(' ');
        const distEl = document.getElementById('ov-rank-dist');
        if (distEl) distEl.innerHTML = distHtml || '—';

        // PSI chart from real evaluation history
        const psiHistory = (metrics.psi_history || []).map((e, i) => ({
          t: '#' + e.index,
          psi: e.reward,
        }));
        if (psiHistory.length > 0) {
          const ctx = document.getElementById('ov-chart')?.getContext('2d');
          if (ctx) {
            if (ovChart) { ovChart.destroy(); ovChart = null; }
            ovChart = CHARTS.createChart('ov-chart', 'line',
              psiHistory.map(d => d.t),
              [
                { label: 'Reward (PSI)', data: psiHistory.map(d => d.psi), borderColor: '#f5a623', backgroundColor: 'rgba(245,166,35,0.05)', tension: 0.3, pointRadius: 0, borderWidth: 1.5, fill: true },
              ]
            );
          }
        }
      }

      // Dependencies from health/ready
      try {
        const ready = await HEALTH_ADAPTER.ready();
        const deps = ready.dependencies || {};
        document.getElementById('gov-deps').innerHTML = Object.entries(deps).map(([k, v]) =>
          '<span class="status-dot"><span class="dot ' + (v ? 'ok' : 'error') + '"></span>' + k + '</span>'
        ).join('');
      } catch (_) {}

      // Certification ladder
      const certLevels = ['blocked', 'observe_only', 'recommend_ready', 'controlled_ready', 'restricted_critical_ready'];
      const certColors = { blocked: '#f87171', observe_only: '#fbbf24', recommend_ready: '#60a5fa', controlled_ready: '#22d3a0', restricted_critical_ready: '#f5a623' };
      const certStrip = document.getElementById('cert-strip');
      if (certStrip) {
        certStrip.innerHTML = '';
        certLevels.forEach((lvl, i) => {
          const d = document.createElement('div');
          d.className = 'cert-step' + (lvl === govStatus.certification_level ? ' active' : '');
          d.textContent = lvl.replace(/_/g, ' ');
          d.style.borderBottomColor = lvl === govStatus.certification_level ? (certColors[lvl] || 'var(--ok)') : 'transparent';
          d.style.background = lvl === govStatus.certification_level ? (certColors[lvl] + '22') : '';
          d.style.color = lvl === govStatus.certification_level ? (certColors[lvl] || '') : '';
          if (i < certLevels.length - 1) d.style.borderRight = 'var(--border)';
          certStrip.appendChild(d);
        });
      }

      // Gateway agents
      try {
        const gwData = await GATEWAY_ADAPTER.listAgents();
        const agents = gwData.agents || [];
        renderGatewayTable(agents);
        CHARTS.drawStateDiagram('state-diagram', agents.map(a => a.state));
      } catch (_) {}

    } catch (e) {
      APP.showToast('Overview load failed: ' + e.message, 'error');
    }
  }

  function renderGatewayTable(agents) {
    const table = document.getElementById('ov-gw-table');
    if (!table) return;
    document.getElementById('ov-agent-count').textContent = agents.length + ' agents via Gateway';
    table.innerHTML = '';
    const hdr = document.createElement('div');
    hdr.className = 'agent-hdr';
    hdr.innerHTML = '<span>Agent</span><span>Role</span><span>State</span><span>Reward</span><span>Trend</span><span>Rank</span>';
    table.appendChild(hdr);
    agents.forEach((a, i) => {
      const r = document.createElement('div');
      r.className = 'agent-row';
      r.style.animation = 'slide-in-left 0.' + (2 + i) + 's ease both';
      const evals = a.evaluations || [];
      const lastRank = evals.length ? evals[evals.length - 1].rank : '—';
      const rc = APP.rankColors[lastRank] || { c: 'var(--muted)', bg: 'transparent' };
      const trendSym = a.trend === 'improving' ? '↑' : a.trend === 'declining' ? '↓' : '→';
      r.innerHTML =
        '<span class="font-mono" style="font-size:11px;color:var(--amber)">' + a.agent_id + '</span>' +
        '<span class="font-data text-ghost" style="font-size:10px">' + (a.role || '—') + '</span>' +
        '<span><span class="gw-state-badge ' + a.state + '" style="font-size:9px">' + a.state + '</span></span>' +
        '<span class="font-mono" style="font-size:12px;color:' + ((a.avg_reward || 0) > 0.5 ? 'var(--ok)' : (a.avg_reward || 0) > 0 ? 'var(--amber)' : 'var(--error)') + '">' + (a.avg_reward || 0).toFixed(2) + '</span>' +
        '<span class="font-mono" style="font-size:11px;color:' + (a.trend === 'improving' ? 'var(--ok)' : a.trend === 'declining' ? 'var(--error)' : 'var(--muted)') + '">' + trendSym + '</span>' +
        '<span class="rank-badge" style="background:' + rc.bg + ';border:1px solid ' + rc.c + '40;color:' + rc.c + ';padding:2px 6px;font-size:9px">' + lastRank + '</span>';
      table.appendChild(r);
    });
  }

  // Animated PSI indicator (uses real latest reward if available)
  setInterval(() => {
    ovTick++;
    const latestEntry = document.getElementById('ov-avg-reward-all');
    const basePsi = latestEntry && latestEntry.textContent !== '—' ? parseFloat(latestEntry.textContent) : 0.612;
    const psi = Math.min(1, Math.max(0, basePsi + Math.sin(ovTick * 0.3) * 0.02));
    const dPsi = (Math.sin(ovTick) * 0.015);
    const kpsi = document.getElementById('kpsi');
    const dpsi = document.getElementById('dpsi');
    const dkpsi = document.getElementById('dkpsi');
    if (kpsi) { kpsi.textContent = psi.toFixed(4); kpsi.style.color = psi > 0.5 ? 'var(--ok)' : 'var(--warn)'; }
    if (dpsi) { dpsi.textContent = dPsi.toFixed(4); dpsi.style.color = Math.abs(dPsi) < 0.02 ? 'var(--ok)' : 'var(--warn)'; }
    if (dkpsi) { dkpsi.textContent = (dPsi >= 0 ? '↑ ' : '↓ ') + Math.abs(dPsi).toFixed(4); dkpsi.className = 'md ' + (dPsi >= 0 ? 'up' : 'dn'); }
  }, 3000);

  return { refresh };
})();
