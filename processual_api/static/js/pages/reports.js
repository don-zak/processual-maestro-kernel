PAGES.reports = (() => {
  let reportsData = [];

  async function refresh() {
    const countEl = document.getElementById('rpt-count');
    try {
      const res = await GOVERNOR_ADAPTER.reports();
      reportsData = res.recent || [];
      const total = res.total || 0;
      if (countEl) countEl.textContent = total + ' evaluations \u00B7 ' + (res.avg_reward || 0).toFixed(4) + ' avg reward';
      renderList();
    } catch (_) {
      if (countEl) countEl.textContent = 'Could not load reports';
    }
  }

  function getFilteredData() {
    const filterRank = document.getElementById('rpt-filter-rank')?.value || '';
    if (!filterRank) return reportsData;
    return reportsData.filter(r => r.rank === filterRank);
  }

  function renderList() {
    const list = document.getElementById('rpt-list');
    if (!list) return;
    list.innerHTML = '';
    const filtered = getFilteredData();
    if (filtered.length === 0) {
      list.innerHTML = '<div class="text-muted font-data" style="font-size:11px;padding:var(--s-2)">No evaluations yet. Run governance on an answer to see reports here.</div>';
      return;
    }

    const table = document.createElement('table');
    table.style.width = '100%';
    table.style.borderCollapse = 'collapse';
    table.style.fontSize = '11px';
    table.innerHTML =
      '<thead><tr style="text-align:left;border-bottom:1px solid rgba(138,163,200,0.1)">' +
      '<th style="padding:6px 8px;color:var(--ghost)">eval_id</th>' +
      '<th style="padding:6px 8px;color:var(--ghost)">Rank</th>' +
      '<th style="padding:6px 8px;color:var(--ghost)">Reward</th>' +
      '<th style="padding:6px 8px;color:var(--ghost)">Policy</th>' +
      '<th style="padding:6px 8px;color:var(--ghost)">Date</th>' +
      '<th style="padding:6px 8px;color:var(--ghost)">Actions</th>' +
      '</tr></thead><tbody>';

    filtered.forEach((r) => {
      const rc = APP.rankColors[r.rank] || { c: '#8aa3c8', bg: 'transparent' };
      const ts = r.ts ? new Date(r.ts).toLocaleString() : '\u2014';
      const eid = r.eval_id || '';
      table.innerHTML +=
        '<tr style="border-bottom:1px solid rgba(138,163,200,0.05);cursor:pointer" data-eval-id="' + eid + '">' +
        '<td style="padding:6px 8px;color:var(--muted);font-family:monospace;font-size:9px;max-width:180px;overflow:hidden;text-overflow:ellipsis" title="' + eid + '">' + (eid ? eid.slice(-16) : '\u2014') + '</td>' +
        '<td style="padding:6px 8px"><span class="rank-badge" style="background:' + rc.bg + ';border:1px solid ' + rc.c + '40;color:' + rc.c + ';font-size:9px;padding:1px 6px">' + (r.rank || '?') + '</span></td>' +
        '<td style="padding:6px 8px;font-family:monospace;color:' + ((r.reward || 0) > 0 ? 'var(--ok)' : 'var(--error)') + '">' + (r.reward || 0).toFixed(4) + '</td>' +
        '<td style="padding:6px 8px"><span class="tag" style="background:rgba(138,163,200,0.094);color:var(--soft);font-size:9px">' + (r.policy || '\u2014') + '</span></td>' +
        '<td style="padding:6px 8px;color:var(--muted)">' + ts + '</td>' +
        '<td style="padding:6px 8px">' +
        '<button class="btn ghost sm" data-pdf-eval-id="' + eid + '" style="font-size:9px;padding:2px 6px">PDF</button>' +
        '<button class="btn ghost sm" data-json-eval-id="' + eid + '" style="font-size:9px;padding:2px 6px;margin-left:4px">JSON</button>' +
        '</td>' +
        '</tr>';
    });

    table.innerHTML += '</tbody>';
    list.appendChild(table);

    table.querySelectorAll('[data-pdf-eval-id]').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const evalId = btn.dataset.pdfEvalId;
        GOVERNOR_ADAPTER.reportPdfById(evalId).then(blob => {
          const url = URL.createObjectURL(blob);
          const a = document.createElement('a');
          a.href = url;
          a.download = 'governance-eval-' + evalId + '.pdf';
          a.click();
          URL.revokeObjectURL(url);
        }).catch(() => APP.showToast('Failed to download PDF', 'error'));
      });
    });

    table.querySelectorAll('[data-json-eval-id]').forEach(btn => {
      btn.addEventListener('click', (e) => {
        e.stopPropagation();
        const evalId = btn.dataset.jsonEvalId;
        const r = reportsData.find(x => x.eval_id === evalId);
        if (!r) return;
        const json = JSON.stringify(r, null, 2);
        const blob = new Blob([json], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'governance-eval-' + evalId + '.json';
        a.click();
        URL.revokeObjectURL(url);
      });
    });

    table.querySelectorAll('tbody tr').forEach(row => {
      row.addEventListener('click', () => {
        const evalId = row.dataset.evalId;
        const r = reportsData.find(x => x.eval_id === evalId);
        if (!r) return;
        const detail = document.getElementById('rpt-detail');
        if (detail) {
          const rc = APP.rankColors[r.rank] || { c: '#8aa3c8', bg: 'transparent' };
          detail.innerHTML =
            '<div class="card flat">' +
            '<div class="flex-between"><span class="font-data text-ghost">eval_id</span><span class="font-mono text-muted" style="font-size:9px;max-width:220px;overflow:hidden;text-overflow:ellipsis" title="' + (r.eval_id || '') + '">' + (r.eval_id || '\u2014') + '</span></div>' +
            '<div class="flex-between" style="margin-top:6px"><span class="font-data text-ghost">Rank</span><span class="rank-badge" style="background:' + rc.bg + ';border:1px solid ' + rc.c + '40;color:' + rc.c + '">' + (r.rank || '?') + '</span></div>' +
            '<div class="flex-between" style="margin-top:6px"><span class="font-data text-ghost">Reward</span><span class="font-mono" style="color:' + ((r.reward || 0) > 0 ? 'var(--ok)' : 'var(--error)') + '">' + (r.reward || 0).toFixed(4) + '</span></div>' +
            '<div class="flex-between" style="margin-top:6px"><span class="font-data text-ghost">Policy</span><span class="tag" style="background:rgba(138,163,200,0.094);color:var(--soft)">' + (r.policy || '\u2014') + '</span></div>' +
            '<div class="flex-between" style="margin-top:6px"><span class="font-data text-ghost">Policy Label</span><span class="font-data">' + (r.policy_label || '\u2014') + '</span></div>' +
            '<div class="flex-between" style="margin-top:6px"><span class="font-data text-ghost">Date</span><span class="font-data">' + (r.ts ? new Date(r.ts).toLocaleString() : '\u2014') + '</span></div>' +
            (r.signature ? '<div class="flex-between" style="margin-top:6px"><span class="font-data text-ghost">Signature</span><span class="font-mono text-muted" style="font-size:8px;max-width:200px;overflow:hidden;text-overflow:ellipsis">' + r.signature + '</span></div>' : '') +
            '</div>';
        }
      });
    });
  }

  async function generateLLMReport() {
    const rank = document.getElementById('llm-rank').value;
    const style = document.getElementById('llm-style').value;
    const provider = document.getElementById('llm-provider').value;
    const fateRaw = document.getElementById('llm-fate').value;

    let fateVector;
    try {
      fateVector = JSON.parse(fateRaw);
    } catch (e) {
      APP.showToast('Invalid Fate Vector JSON', 'error');
      return;
    }

    const btn = document.getElementById('llm-report-btn');
    const outputEl = document.getElementById('llm-report-output');
    const metaEl = document.getElementById('llm-report-meta');
    const statusEl = document.getElementById('llm-report-status');

    APP.showLoading('llm-report-btn', 'Generating...');
    outputEl.textContent = '';
    metaEl.textContent = '';

    try {
      const res = await CLIENT.post('/reports/generate-llm', {
        fate_vector: fateVector,
        existence_rank: rank,
        provider: provider,
        style: style,
        language: 'en',
      });

      outputEl.textContent = res.report || 'No report generated';
      if (res.latency_ms !== undefined) {
        metaEl.textContent = 'Provider: ' + res.provider_used + ' \u00B7 Model: ' + (res.model_used || '-') + ' \u00B7 ' + res.latency_ms + 'ms';
        if (res.tokens_used) {
          metaEl.textContent += ' \u00B7 Tokens: ' + JSON.stringify(res.tokens_used);
        }
      }
      statusEl.textContent = '\u2713 Report generated';
      APP.showToast('AI report generated', 'success');
    } catch (e) {
      outputEl.textContent = 'Error: ' + (e.detail || e.message);
      statusEl.textContent = '\u2717 Generation failed \u2014 configure LLM provider in Settings';
      APP.showToast('AI report failed: ' + (e.detail || e.message), 'error');
    } finally {
      APP.hideLoading('llm-report-btn');
    }
  }

  function init() {
    refresh();

    document.getElementById('fat-submit')?.addEventListener('click', async () => {
      const wf = document.getElementById('fat-wf').value;
      const rank = document.getElementById('fat-rank').value;
      const resultDiv = document.getElementById('fat-result');
      if (!wf) { resultDiv.innerHTML = '<span class="font-data text-warn" style="font-size:11px">Enter workflow ID</span>'; return; }
      try {
        const res = await CLIENT.post('/reports/fate', { workflow_id: wf, fate_vector: {}, existence_rank: rank });
        resultDiv.innerHTML = '<span class="font-data" style="font-size:11px;color:var(--ok)">Fate report recorded</span>';
        APP.showToast('Fate report submitted', 'success');
      } catch (e) {
        resultDiv.innerHTML = '<span class="font-data" style="font-size:11px;color:var(--error)">Error: ' + (e.detail || e.message) + '</span>';
      }
    });

    document.getElementById('llm-report-btn')?.addEventListener('click', generateLLMReport);

    document.getElementById('rpt-filter-rank')?.addEventListener('change', renderList);
    document.getElementById('rpt-refresh-btn')?.addEventListener('click', refresh);
  }

  if (document.readyState !== 'loading') init(); else document.addEventListener('DOMContentLoaded', init);
  return { refresh };
})();
