PAGES.governor = (() => {
  let govRadarChart = null;

  const CGT_DEFAULTS = {
    compatibility: 0.6, coherence: 0.5, structural_support: 0.5,
    usefulness: 0.6, complexity: 0.4, fatigue: 0.3, shock: 0.2,
    lift: 0.5, novelty: 0.4, no_answer: 0.1, hallucination: 0.1,
    constraint_failure: 0.1, speed: 0.5
  };

  let govState = { ...CGT_DEFAULTS, answer: '', clientQuery: '' };

  function isAutoMode() {
    return document.getElementById('gov-auto-toggle')?.checked || false;
  }

  function toggleMode() {
    const auto = isAutoMode();
    document.getElementById('gov-auto-section').style.display = auto ? 'block' : 'none';
    document.getElementById('gov-manual-section').style.display = auto ? 'none' : 'block';
    if (auto) {
      document.getElementById('gov-params').innerHTML = '';
    } else {
      renderParams();
    }
  }

  async function refresh() {
    try {
      const st = await GOVERNOR_ADAPTER.status();
      document.getElementById('gov-evaluate-btn').textContent = st.enabled ? 'Evaluate via Governor' : 'Governor Disabled';
    } catch (_) {}
    toggleMode();
  }

  function renderParams() {
    const container = document.getElementById('gov-params');
    if (!container) return;
    container.innerHTML = '';
    const params = [
      { key: 'compatibility', label: 'Compatibility', min: 0, max: 1, step: 0.05 },
      { key: 'coherence', label: 'Coherence', min: 0, max: 1, step: 0.05 },
      { key: 'structural_support', label: 'Structural Support', min: 0, max: 1, step: 0.05 },
      { key: 'usefulness', label: 'Usefulness', min: 0, max: 1, step: 0.05 },
      { key: 'complexity', label: 'Complexity', min: 0, max: 1, step: 0.05 },
      { key: 'fatigue', label: 'Fatigue', min: 0, max: 1, step: 0.05 },
      { key: 'shock', label: 'Shock', min: 0, max: 1, step: 0.05 },
      { key: 'lift', label: 'Lift', min: 0, max: 1, step: 0.05 },
      { key: 'novelty', label: 'Novelty', min: 0, max: 1, step: 0.05 },
      { key: 'no_answer', label: 'No Answer Risk', min: 0, max: 1, step: 0.05 },
      { key: 'hallucination', label: 'Hallucination Risk', min: 0, max: 1, step: 0.05 },
      { key: 'constraint_failure', label: 'Constraint Failure', min: 0, max: 1, step: 0.05 },
    ];

    params.forEach(p => {
      const group = document.createElement('div');
      group.className = 'slider-group';
      group.innerHTML =
        '<div class="sl-hdr"><span>' + p.label + '</span><span id="gov-val-' + p.key + '">' + govState[p.key].toFixed(2) + '</span></div>' +
        '<input type="range" id="gov-slider-' + p.key + '" min="' + p.min + '" max="' + p.max + '" step="' + p.step + '" value="' + govState[p.key] + '">';
      container.appendChild(group);

      document.getElementById('gov-slider-' + p.key).addEventListener('input', (e) => {
        govState[p.key] = parseFloat(e.target.value);
        document.getElementById('gov-val-' + p.key).textContent = govState[p.key].toFixed(2);
      });
    });
  }

  async function evaluate() {
    const answer = document.getElementById('gov-answer').value.trim();
    if (!answer) { APP.showToast('Please enter an agent answer', 'warn'); return; }

    const auto = isAutoMode();
    let params;

    if (auto) {
      const clientQuery = document.getElementById('gov-client-query').value.trim();
      if (!clientQuery) {
        APP.showToast('Please enter a Client Query for auto analysis', 'warn');
        return;
      }
      docgovNoQueryWarn(false);
      params = { answer, client_query: clientQuery };
    } else {
      params = { ...govState, answer };
    }

    APP.showLoading('gov-evaluate-btn', 'Evaluating...');
    try {
      const res = await GOVERNOR_ADAPTER.evaluate(params);
      displayResults(res);
      APP.showToast('Evaluation: ' + (res.rank || '—') + ' | Reward: ' + (res.reward || 0).toFixed(4), 'success');
    } catch (e) {
      APP.showToast('Evaluation failed: ' + (e.detail || e.message), 'error');
    }
    APP.hideLoading('gov-evaluate-btn');
  }

  function docgovNoQueryWarn(show) {
    const el = document.getElementById('gov-no-query-warn');
    if (el) el.style.display = show ? 'block' : 'none';
  }

  function displayResults(res) {
    const container = document.getElementById('gov-results');
    const copyBtn = document.getElementById('gov-copy-repair');
    const rewardBar = document.getElementById('gov-reward-bar');
    const rewardLabel = document.getElementById('gov-reward-label');

    if (!container) return;

    const reward = res.reward || 0;
    const rank = res.rank || 'unknown';
    const rc = APP.rankColors[rank] || { c: '#8aa3c8', bg: 'transparent' };

    if (rewardBar) {
      const pct = Math.max(0, Math.min(100, (reward + 2) / 4 * 100));
      rewardBar.style.width = pct + '%';
      rewardBar.style.background = reward > 0.5 ? 'var(--ok)' : reward > 0 ? 'var(--amber)' : 'var(--error)';
    }
    if (rewardLabel) {
      rewardLabel.textContent = rank;
      rewardLabel.style.background = rc.bg;
      rewardLabel.style.color = rc.c;
      rewardLabel.style.border = '1px solid ' + rc.c + '40';
    }

    container.innerHTML =
      '<div class="card flat" style="margin-top:var(--s-2)">' +
      '<div class="flex-gap" style="margin-bottom:var(--s-3)">' +
      '<span class="rank-badge" style="background:' + rc.bg + ';border:1px solid ' + rc.c + '40;color:' + rc.c + '"><span class="rdot" style="background:' + rc.c + '"></span>' + rank + '</span>' +
      '<span class="font-mono" style="font-size:13px;color:' + (reward > 0 ? 'var(--ok)' : 'var(--error)') + '">' + (reward > 0 ? '+' : '') + reward.toFixed(4) + '</span>' +
      '</div>' +
      (res.policy ? '<div class="flex-between"><span class="font-data text-ghost" style="font-size:11px">Policy</span><span class="tag" style="background:rgba(138,163,200,0.094);color:var(--soft)">' + res.policy + '</span></div>' : '') +
      (res.policy_label ? '<div class="flex-between" style="margin-top:4px"><span class="font-data text-ghost" style="font-size:11px">Action</span><span class="font-data" style="font-size:11px">' + res.policy_label + '</span></div>' : '') +
      (res.repair_prompt ? '<div class="flex-between" style="margin-top:4px"><span class="font-data text-ghost" style="font-size:11px">Repair</span><span class="font-data text-soft" style="font-size:11px">' + res.repair_prompt.substring(0, 100) + '...</span></div>' : '') +
      (res.signature ? '<div class="flex-between" style="margin-top:4px"><span class="font-data text-ghost" style="font-size:11px">SHA3-256</span><span class="font-mono text-muted" style="font-size:8px;max-width:200px;overflow:hidden;text-overflow:ellipsis">' + res.signature + '</span></div>' : '') +
      '</div>';

    if (copyBtn) {
      copyBtn.style.display = res.repair_prompt ? 'block' : 'none';
      copyBtn.onclick = () => {
        navigator.clipboard.writeText(res.repair_prompt || '');
        APP.showToast('Repair prompt copied', 'success');
      };
    }

    if (res.fate_vector) {
      drawRadar(res.fate_vector);
    }
  }

  function drawRadar(fateVector) {
    const canvas = document.getElementById('gov-radar');
    if (!canvas) return;
    const labels = Object.keys(fateVector);
    const values = labels.map(k => Math.abs(fateVector[k] * 100));
    if (govRadarChart) { govRadarChart.destroy(); }
    govRadarChart = CHARTS.createChart('gov-radar', 'radar', labels,
      [{ label: 'Fate Vector', data: values, backgroundColor: 'rgba(245,166,35,0.1)', borderColor: '#f5a623', pointBackgroundColor: '#f5a623', borderWidth: 1.5 }],
      { scales: { r: { beginAtZero: true, max: 100, grid: { color: 'rgba(42,54,80,0.3)' }, ticks: { color: '#5a7299', backdropColor: 'transparent' } } },
        plugins: { legend: { display: false } } }
    );
  }

  function init() {
    document.getElementById('gov-answer')?.addEventListener('input', (e) => { govState.answer = e.target.value; });
    document.getElementById('gov-evaluate-btn')?.addEventListener('click', evaluate);
    document.getElementById('gov-auto-toggle')?.addEventListener('change', toggleMode);
    document.getElementById('gov-client-query')?.addEventListener('input', (e) => {
      govState.clientQuery = e.target.value;
      docgovNoQueryWarn(false);
    });
    refresh();
  }

  if (document.readyState !== 'loading') init(); else document.addEventListener('DOMContentLoaded', init);

  return { refresh, evaluate };
})();