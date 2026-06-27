PAGES.telemetry = (() => {
  let telChart = null;
  let telStreaming = true;
  let telTick = 0;
  let telInterval = null;

  const METRICS = {
    psi:        { label: 'Kernel PSI',       color: '#f5a623', data: [] },
    drift:      { label: 'Drift',            color: '#f87171', data: [] },
    latency:    { label: 'Latency',          color: '#4aaef5', data: [] },
    throughput: { label: 'Throughput',       color: '#22d3a0', data: [] },
  };
  let selectedMetric = 'psi';

  function init() {
    // Prime data
    Object.keys(METRICS).forEach(k => {
      METRICS[k].data = Array.from({ length: 60 }, (_, i) => ({ t: i, v: Math.sin(i * 0.2) * 0.2 + 0.5 + Math.random() * 0.1 }));
    });

    renderMetricsSelector();
    selectMetric('psi');
    telInterval = setInterval(tick, 2000);

    document.getElementById('tel-toggle')?.addEventListener('click', () => {
      telStreaming = !telStreaming;
      document.getElementById('tel-toggle').textContent = telStreaming ? 'Pause' : 'Resume';
      document.getElementById('tel-status').textContent = telStreaming ? 'Streaming' : 'Paused';
      document.getElementById('tel-status').style.color = telStreaming ? 'var(--ok)' : 'var(--warn)';
    });
    document.getElementById('ingest-btn')?.addEventListener('click', async () => {
      const metric = document.getElementById('ingest-metric').value;
      const value = parseFloat(document.getElementById('ingest-value').value);
      if (isNaN(value)) { APP.showToast('Enter a valid number', 'warn'); return; }
      try {
        await TELEMETRY_ADAPTER.ingest([{ metric, value, labels: {} }]);
        APP.showToast('Ingested ' + metric + ' = ' + value, 'success');
      } catch (e) {
        APP.showToast('Ingest failed: ' + (e.detail || e.message), 'error');
      }
    });
  }

  function renderMetricsSelector() {
    const container = document.getElementById('tel-metrics');
    if (!container) return;
    container.innerHTML = '';
    Object.entries(METRICS).forEach(([key, m]) => {
      const chip = document.createElement('span');
      chip.className = 'tel-chip' + (key === selectedMetric ? ' active' : '');
      chip.textContent = m.label;
      chip.style.borderLeft = '2px solid ' + m.color;
      chip.addEventListener('click', () => selectMetric(key));
      container.appendChild(chip);
    });
  }

  function selectMetric(key) {
    selectedMetric = key;
    document.querySelectorAll('.tel-chip').forEach(c => c.classList.remove('active'));
    renderMetricsSelector();
    renderTelemetryChart();

    const m = METRICS[key];
    document.getElementById('tel-metric-title').textContent = m.label;
    document.getElementById('tel-metric-sub').textContent = 'Last 60 observations · current: ' + (m.data.length ? m.data[m.data.length - 1].v.toFixed(4) : '—');
    document.getElementById('tel-current').textContent = m.data.length ? m.data[m.data.length - 1].v.toFixed(4) : '—';
    document.getElementById('tel-current').style.color = m.color;
  }

  function renderTelemetryChart() {
    const canvas = document.getElementById('tel-chart');
    if (!canvas) return;
    const m = METRICS[selectedMetric];
    if (telChart) { telChart.destroy(); telChart = null; }
    if (m.data.length) {
      telChart = CHARTS.createChart('tel-chart', 'line',
        m.data.map(d => d.t),
        [{ label: m.label, data: m.data.map(d => d.v), borderColor: m.color, backgroundColor: m.color + '20', tension: 0.3, pointRadius: 0, borderWidth: 1.5, fill: true }],
        { scales: { y: { grid: { color: 'rgba(42,54,80,0.3)' }, ticks: { color: '#5a7299', font: { size: 9 } } } },
          plugins: { legend: { display: false } } }
      );
    }
  }

  function tick() {
    if (!telStreaming) return;
    telTick++;
    document.getElementById('tel-ticks').textContent = telTick;
    Object.entries(METRICS).forEach(([key, m]) => {
      m.data.push({ t: m.data.length, v: m.data[m.data.length - 1].v + (Math.random() - 0.5) * 0.05 });
      if (m.data.length > 60) m.data.shift();
    });
    if (selectedMetric) {
      const m = METRICS[selectedMetric];
      document.getElementById('tel-current').textContent = m.data.length ? m.data[m.data.length - 1].v.toFixed(4) : '—';
    }
    renderTelemetryChart();
  }

  if (document.readyState !== 'loading') init(); else document.addEventListener('DOMContentLoaded', init);
  return {};
})();
