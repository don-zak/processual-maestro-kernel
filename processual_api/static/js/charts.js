const CHARTS = (() => {

  function makeCanvas(id, w, h) {
    const c = document.getElementById(id);
    if (!c) return null;
    c.width = w || c.parentElement.clientWidth || 340;
    c.height = h || c.parentElement.clientHeight || 130;
    return c.getContext('2d');
  }

  function drawGauge(canvasId, value, min, max) {
    const ctx = makeCanvas(canvasId);
    if (!ctx) return;
    const c = document.getElementById(canvasId);
    const w = c.width, h = c.height;
    const cx = w / 2, cy = h * 0.65, r = Math.min(w, h) * 0.35;

    ctx.clearRect(0, 0, w, h);
    const pct = (value - min) / (max - min);
    const angle = -Math.PI * 0.75 + pct * Math.PI * 1.5;
    const color = pct > 0.6 ? '#22d3a0' : pct > 0.3 ? '#fbbf24' : '#f87171';

    ctx.strokeStyle = '#1d2638';
    ctx.lineWidth = 8;
    ctx.beginPath();
    ctx.arc(cx, cy, r, -Math.PI * 0.75, Math.PI * 0.75);
    ctx.stroke();

    ctx.strokeStyle = color;
    ctx.lineWidth = 6;
    ctx.shadowColor = color;
    ctx.shadowBlur = 8;
    ctx.beginPath();
    ctx.arc(cx, cy, r, -Math.PI * 0.75, angle);
    ctx.stroke();
    ctx.shadowBlur = 0;

    ctx.fillStyle = color;
    ctx.font = '18px "Space Mono",monospace';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText((value >= 0 ? '+' : '') + value.toFixed(2), cx, cy);
  }

  function drawTrendChart(canvasId, evaluations) {
    const canvas = document.getElementById(canvasId);
    if (!canvas || !evaluations || evaluations.length < 2) return;
    const ctx = canvas.getContext('2d');
    const w = canvas.width = canvas.parentElement.clientWidth || 340;
    const h = canvas.height = 130;
    const pad = { top: 10, bottom: 20, left: 10, right: 10 };
    const cw = w - pad.left - pad.right, ch = h - pad.top - pad.bottom;
    const rewards = evaluations.map(e => e.reward);
    const mn = Math.min(...rewards), mx = Math.max(...rewards);
    const range = mx - mn || 1;

    ctx.clearRect(0, 0, w, h);
    ctx.strokeStyle = '#2a3650';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(pad.left, pad.top + ch / 2);
    ctx.lineTo(w - pad.right, pad.top + ch / 2);
    ctx.stroke();

    ctx.strokeStyle = '#f5a623';
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    evaluations.forEach((e, i) => {
      const x = pad.left + (i / (evaluations.length - 1)) * cw;
      const y = pad.top + ch - ((e.reward - mn) / range) * ch;
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
    });
    ctx.stroke();

    evaluations.forEach((e, i) => {
      if (i % Math.max(1, Math.floor(evaluations.length / 8)) !== 0) return;
      const x = pad.left + (i / (evaluations.length - 1)) * cw;
      ctx.fillStyle = '#3d5070';
      ctx.font = '8px "DM Mono",monospace';
      ctx.textAlign = 'center';
      ctx.fillText(e.reward.toFixed(2), x, h - 2);
    });
  }

  function drawStateDiagram(canvasId, states) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const w = canvas.width = canvas.parentElement.clientWidth || 340;
    const h = canvas.height = 150;
    const nodes = [
      { id: 'active',        label: 'Active',       x: w * 0.5,  y: 20,  color: '#22d3a0' },
      { id: 'pending',       label: 'Pending',      x: w * 0.5,  y: 70,  color: '#fbbf24' },
      { id: 'frozen',        label: 'Frozen',       x: w * 0.15, y: 70,  color: '#60a5fa' },
      { id: 'escalated',     label: 'Escalated',    x: w * 0.85, y: 70,  color: '#fb923c' },
      { id: 'rehabilitating',label: 'Rehab',        x: w * 0.5,  y: 120, color: '#a78bfa' },
      { id: 'deactivated',   label: 'Deactivated',  x: w * 0.5,  y: 170, color: '#f87171' },
    ];

    const count = {};
    (states || []).forEach(s => { count[s] = (count[s] || 0) + 1; });

    ctx.clearRect(0, 0, w, h);
    ctx.strokeStyle = '#2a3650';
    ctx.lineWidth = 1;
    const edges = [
      ['pending', 'active'], ['active', 'frozen'], ['active', 'escalated'],
      ['frozen', 'rehabilitating'], ['escalated', 'rehabilitating'],
      ['rehabilitating', 'active'], ['active', 'deactivated'],
      ['pending', 'deactivated'],
    ];
    edges.forEach(([a, b]) => {
      const na = nodes.find(n => n.id === a), nb = nodes.find(n => n.id === b);
      if (!na || !nb) return;
      ctx.beginPath();
      ctx.moveTo(na.x, na.y);
      ctx.lineTo(nb.x, nb.y);
      ctx.stroke();
    });

    nodes.forEach(n => {
      const c = count[n.id] || 0;
      ctx.beginPath();
      ctx.arc(n.x, n.y, 14, 0, Math.PI * 2);
      ctx.fillStyle = n.color + '22';
      ctx.fill();
      ctx.strokeStyle = n.color;
      ctx.lineWidth = c > 0 ? 2 : 1;
      ctx.stroke();
      ctx.fillStyle = '#c8d8f0';
      ctx.font = '8px "Space Mono",monospace';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(c, n.x, n.y);
      ctx.fillStyle = '#8aa3c8';
      ctx.font = '7px "DM Mono",monospace';
      ctx.textBaseline = 'top';
      ctx.fillText(n.label, n.x, n.y + 16);
    });
  }

  function createChart(canvasId, type, labels, datasets, opts) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return null;
    const ctx = canvas.getContext('2d');
    return new Chart(ctx, {
      type,
      data: { labels, datasets },
      options: {
        responsive: true, maintainAspectRatio: false,
        plugins: { legend: { display: false }, tooltip: { backgroundColor: '#1d2638', borderColor: '#2a3650', borderWidth: 1, titleFont: { size: 11 }, bodyFont: { size: 11 } } },
        scales: {
          x: { grid: { display: false }, ticks: { color: '#5a7299', font: { size: 9 }, maxTicksLimit: 6 } },
          y: { grid: { color: 'rgba(42,54,80,0.5)' }, ticks: { color: '#5a7299', font: { size: 9 } } },
        },
        ...opts,
      }
    });
  }

  return { drawGauge, drawTrendChart, drawStateDiagram, createChart };
})();
