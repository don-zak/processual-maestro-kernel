PAGES.cgt = (() => {
  let cgtRadarChart = null;

  const PARAMS = ['transition_channel','compatibility','retention','harmony','fatigue','complexity','shock','dwell_time','carrier','diversity','novelty','lift'];
  const STATE = {};
  PARAMS.forEach(p => { STATE[p] = 0.5; });

  function renderParams() {
    const container = document.getElementById('cgt-params');
    if (!container) return;
    container.innerHTML = '';
    PARAMS.forEach(p => {
      const g = document.createElement('div');
      g.className = 'slider-group';
      g.innerHTML = '<div class="sl-hdr"><span>' + p.replace(/_/g, ' ') + '</span><span id="cgt-val-' + p + '">0.50</span></div><input type="range" id="cgt-slider-' + p + '" min="0" max="1" step="0.05" value="0.5">';
      container.appendChild(g);
      document.getElementById('cgt-slider-' + p).addEventListener('input', (e) => {
        STATE[p] = parseFloat(e.target.value);
        document.getElementById('cgt-val-' + p).textContent = STATE[p].toFixed(2);
      });
    });
  }

  async function evaluate() {
    APP.showLoading('cgt-eval-btn', 'Evaluating...');
    try {
      const res = await CGT_ADAPTER.evaluate(STATE);
      const rank = res.existence_rank || 'unknown';
      const fv = res.fate_vector || {};
      document.getElementById('cgt-empty').style.display = 'none';
      document.getElementById('cgt-results').innerHTML = '<div class="card flat"><div class="flex-between"><span class="font-data text-ghost" style="font-size:11px">Existence Rank</span><span class="rank-badge" style="background:rgba(34,211,160,0.1);color:#22d3a0;border:1px solid rgba(34,211,160,0.3)">' + rank + '</span></div></div>';

      // Radar chart
      const labels = Object.keys(fv);
      const vals = labels.map(k => Math.abs((fv[k] || 0) * 100));
      const canvas = document.getElementById('cgt-radar');
      if (canvas && labels.length) {
        if (cgtRadarChart) cgtRadarChart.destroy();
        cgtRadarChart = CHARTS.createChart('cgt-radar', 'radar', labels,
          [{ label: 'Fate Vector', data: vals, backgroundColor: 'rgba(245,166,35,0.1)', borderColor: '#f5a623', pointBackgroundColor: '#f5a623', borderWidth: 1.5 }],
          { scales: { r: { beginAtZero: true, max: 100, grid: { color: 'rgba(42,54,80,0.3)' }, ticks: { color: '#5a7299', backdropColor: 'transparent' } } },
            plugins: { legend: { display: false } } }
        );
      }

      // Bars
      const barsDiv = document.getElementById('cgt-bars');
      if (barsDiv && labels.length) {
        barsDiv.innerHTML = labels.map(k =>
          '<div class="progress"><div class="pl"><span>' + k + '</span><span class="font-mono" style="color:' + ((fv[k] || 0) > 0 ? 'var(--ok)' : 'var(--error)') + '">' + (fv[k] || 0).toFixed(3) + '</span></div><div class="pb"><div class="pf" style="width:' + Math.abs((fv[k] || 0) * 100) + '%;background:' + ((fv[k] || 0) > 0 ? 'var(--ok)' : 'var(--error)') + '"></div></div></div>'
        ).join('');
      }
      APP.showToast('CGT Evaluation: ' + rank, 'success');
    } catch (e) {
      APP.showToast('CGT evaluation failed: ' + (e.detail || e.message), 'error');
    }
    APP.hideLoading('cgt-eval-btn');
  }

  function init() {
    renderParams();
    document.getElementById('cgt-eval-btn')?.addEventListener('click', evaluate);
  }

  if (document.readyState !== 'loading') init(); else document.addEventListener('DOMContentLoaded', init);
  return {};
})();
