PAGES.simulation = (() => {
  let simChart = null;

  const SIM_PERSONAS = [
    { id: 'zahrawi', name: 'Al-Zahrawi', role: 'Surgeon & Innovator', field: 'Surgery' },
    { id: 'sina', name: 'Ibn Sina', role: 'Physician & Polymath', field: 'Medicine' },
    { id: 'jabir', name: 'Jabir ibn Hayyan', role: 'Chemist & Alchemist', field: 'Chemistry' },
    { id: 'khwarizmi', name: 'Al-Khwarizmi', role: 'Mathematician & Astronomer', field: 'Mathematics' },
    { id: 'haytham', name: 'Ibn al-Haytham', role: 'Physicist & Vision Scientist', field: 'Optics' },
    { id: 'razi', name: 'Al-Razi', role: 'Physician & Alchemist', field: 'Medicine' },
  ];

  function renderPersonas() {
    const container = document.getElementById('sim-persona-cards');
    if (!container) return;
    container.innerHTML = '';
    SIM_PERSONAS.forEach(p => {
      const card = document.createElement('div');
      card.className = 'card flat';
      card.style.textAlign = 'center';
      card.innerHTML =
        '<div class="font-mono" style="font-size:16px;color:var(--amber);font-weight:700">' + p.name + '</div>' +
        '<div class="font-data text-ghost" style="font-size:10px;margin-top:4px">' + p.role + '</div>' +
        '<div class="tag" style="margin-top:6px;background:rgba(138,163,200,0.094);color:var(--soft)">' + p.field + '</div>';
      container.appendChild(card);
    });
  }

  async function run() {
    APP.showLoading('sim-run-btn', 'Running...');
    document.getElementById('sim-before').style.display = 'none';
    document.getElementById('sim-after').style.display = 'block';
    try {
      const res = await SIMULATION_ADAPTER.run();
      displayResults(res);
      APP.showToast('Simulation complete: ' + res.total_agents + ' agents evaluated', 'success');
    } catch (e) {
      APP.showToast('Simulation failed: ' + (e.detail || e.message), 'error');
      document.getElementById('sim-before').style.display = 'block';
      document.getElementById('sim-after').style.display = 'none';
    }
    APP.hideLoading('sim-run-btn');
  }

  function displayResults(res) {
    const agents = res.agents || [];
    const rankDist = res.rank_distribution || {};
    const rankColorsMap = {
      flourishing: '#22d3a0', stable: '#4aaef5', hybrid: '#a78bfa',
      distorted: '#fb923c', transient: '#fbbf24', extinct: '#f87171'
    };

    // Summary
    const summaryEl = document.getElementById('sim-summary');
    if (summaryEl) {
      const best = agents.reduce((best, a) => (a.reward || 0) > (best.reward || -Infinity) ? a : best, agents[0] || {});
      const worst = agents.reduce((worst, a) => (a.reward || Infinity) < (worst.reward || Infinity) ? a : worst, agents[0] || {});
      summaryEl.innerHTML =
        '<div class="flex-between"><span class="font-data text-ghost" style="font-size:11px">Total Agents</span><span class="font-mono" style="font-size:13px">' + (res.total_agents || agents.length) + '</span></div>' +
        '<div class="flex-between" style="margin-top:6px"><span class="font-data text-ghost" style="font-size:11px">Avg Reward</span><span class="font-mono" style="font-size:13px;color:' + ((res.avg_reward || 0) > 0 ? 'var(--ok)' : 'var(--error)') + '">' + (res.avg_reward || 0).toFixed(4) + '</span></div>' +
        '<div class="flex-between" style="margin-top:6px"><span class="font-data text-ghost" style="font-size:11px">Highest</span><span class="font-mono" style="font-size:11px;color:var(--ok)">' + (best.name || best.id || '—') + ' (' + (best.reward || 0).toFixed(2) + ')</span></div>' +
        '<div class="flex-between" style="margin-top:6px"><span class="font-data text-ghost" style="font-size:11px">Lowest</span><span class="font-mono" style="font-size:11px;color:var(--error)">' + (worst.name || worst.id || '—') + ' (' + (worst.reward || 0).toFixed(2) + ')</span></div>' +
        '<div class="flex-between" style="margin-top:6px"><span class="font-data text-ghost" style="font-size:11px">At Risk</span><span class="font-mono" style="font-size:13px;color:' + ((res.risk_count || 0) > 0 ? 'var(--error)' : 'var(--ok)') + '">' + (res.risk_count || 0) + '</span></div>';
    }

    // Signature
    const sigEl = document.getElementById('sim-sig');
    if (sigEl) sigEl.textContent = res.signature || '—';

    // Rank distribution chart
    const chartCanvas = document.getElementById('sim-chart');
    if (chartCanvas) {
      if (simChart) { simChart.destroy(); }
      const labels = Object.keys(rankDist);
      const data = Object.values(rankDist);
      if (labels.length) {
        simChart = CHARTS.createChart('sim-chart', 'bar', labels,
          [{ label: 'Agents', data, backgroundColor: labels.map(l => rankColorsMap[l] || '#3d5070'), borderRadius: 4 }],
          { scales: { y: { beginAtZero: true, grid: { color: 'rgba(42,54,80,0.3)' }, ticks: { color: '#5a7299', font: { size: 9 } } }, x: { grid: { display: false }, ticks: { color: '#8aa3c8', font: { size: 9 } } } },
            plugins: { legend: { display: false } } }
        );
      }
    }

    // Agent cards
    const cardsContainer = document.getElementById('sim-agent-cards');
    if (cardsContainer) {
      cardsContainer.innerHTML = '';
      agents.forEach(a => {
        const rc = APP.rankColors[a.rank] || { c: 'var(--muted)', bg: 'transparent' };
        const card = document.createElement('div');
        card.className = 'card flat';
        card.innerHTML =
          '<div class="flex-between"><span class="font-mono" style="font-size:12px;color:var(--amber);font-weight:600">' + (a.name || a.id) + '</span><span class="rank-badge" style="background:' + rc.bg + ';border:1px solid ' + rc.c + '40;color:' + rc.c + ';padding:2px 8px;font-size:9px">' + (a.rank || '—') + '</span></div>' +
          '<div class="flex-between" style="margin-top:6px"><span class="font-data text-ghost" style="font-size:9px">Reward</span><span class="font-mono" style="font-size:12px;color:' + ((a.reward || 0) > 0 ? 'var(--ok)' : 'var(--error)') + '">' + (a.reward || 0).toFixed(4) + '</span></div>' +
          (a.fate_vector ? '<div style="margin-top:4px"><span class="font-data text-ghost" style="font-size:8px">Fate: ' + Object.entries(a.fate_vector).map(([k, v]) => k + '=' + v.toFixed(2)).join(' ') + '</span></div>' : '') +
          (a.verdict ? '<div style="margin-top:4px"><span class="font-data" style="font-size:10px;color:var(--soft)">' + a.verdict + '</span></div>' : '');
        cardsContainer.appendChild(card);
      });
    }
  }

  function init() {
    renderPersonas();
    document.getElementById('sim-run-btn')?.addEventListener('click', run);
    document.getElementById('sim-copy-sig')?.addEventListener('click', () => {
      const sig = document.getElementById('sim-sig')?.textContent;
      if (sig && sig !== '—') { navigator.clipboard.writeText(sig); APP.showToast('Signature copied', 'success'); }
    });
    document.getElementById('sim-pdf-btn')?.addEventListener('click', async () => {
      const sig = document.getElementById('sim-sig')?.textContent;
      if (sig && sig !== '—') {
        try {
          const blob = await SIMULATION_ADAPTER.reportPdf(sig.replace('sha3:', ''));
          const url = URL.createObjectURL(blob);
          const a = document.createElement('a'); a.href = url; a.download = 'supervision-report.pdf'; a.click();
          URL.revokeObjectURL(url);
          APP.showToast('PDF downloaded', 'success');
        } catch (_) { APP.showToast('PDF download failed', 'error'); }
      }
    });
  }

  if (document.readyState !== 'loading') init(); else document.addEventListener('DOMContentLoaded', init);

  return { refresh: renderPersonas };
})();
