# ruff: noqa: E501

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any


def _safe(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, tuple):
        return [_safe(v) for v in value]
    if isinstance(value, list):
        return [_safe(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _safe(v) for k, v in value.items()}
    return value


_HTML_TEMPLATE = r"""<!doctype html>
<html lang="ar" dir="rtl">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Maestro Adaptive Governance Dashboard</title>
  <style>
    :root { --bg:#0f172a; --panel:#111827; --card:#1f2937; --muted:#94a3b8; --text:#f8fafc; --accent:#38bdf8; --ok:#22c55e; --warn:#f59e0b; --bad:#ef4444; }
    * { box-sizing:border-box; }
    body { margin:0; font-family: system-ui, -apple-system, Segoe UI, sans-serif; background:linear-gradient(135deg,#0f172a,#111827 60%,#172554); color:var(--text); }
    header { padding:32px 24px 16px; max-width:1180px; margin:auto; }
    h1 { margin:0 0 8px; font-size:clamp(28px,4vw,46px); letter-spacing:-.03em; }
    .sub { color:var(--muted); max-width:850px; line-height:1.7; }
    main { max-width:1180px; margin:auto; padding:16px 24px 40px; }
    .toolbar { display:flex; gap:12px; flex-wrap:wrap; align-items:center; margin:16px 0 22px; }
    button, label.file { border:0; background:var(--accent); color:#082f49; padding:10px 14px; border-radius:14px; font-weight:700; cursor:pointer; }
    input[type=file] { display:none; }
    .grid { display:grid; grid-template-columns:repeat(12,1fr); gap:16px; }
    .card { grid-column:span 4; background:rgba(31,41,55,.88); border:1px solid rgba(148,163,184,.18); border-radius:22px; padding:18px; box-shadow:0 18px 50px rgba(0,0,0,.25); }
    .wide { grid-column:span 8; } .full { grid-column:1/-1; }
    .k { color:var(--muted); font-size:13px; } .v { font-size:25px; font-weight:800; margin-top:4px; overflow-wrap:anywhere; }
    .pill { display:inline-block; padding:5px 9px; border-radius:999px; background:rgba(56,189,248,.15); color:#bae6fd; font-size:12px; margin:3px; }
    .ok { color:var(--ok); } .warn { color:var(--warn); } .bad { color:var(--bad); }
    table { width:100%; border-collapse:collapse; } th,td { text-align:right; padding:10px; border-bottom:1px solid rgba(148,163,184,.14); } th { color:#cbd5e1; }
    pre { direction:ltr; text-align:left; white-space:pre-wrap; max-height:360px; overflow:auto; background:#020617; border-radius:16px; padding:16px; color:#dbeafe; }
    @media (max-width:900px) { .card,.wide { grid-column:1/-1; } }
  </style>
</head>
<body>
  <header>
    <h1>Maestro Adaptive Governance</h1>
    <div class="sub">واجهة HTML مستقلة للمراجعة الآمنة. يمكن تحميل UI snapshot أو evidence pack بصيغة JSON. لا تطلب مفاتيح التشفير ولا تفك تشفير التقارير؛ تعرض فهارس وعدادات وآثار تدقيق خفيفة فقط.</div>
  </header>
  <main>
    <div class="toolbar">
      <label class="file">تحميل JSON للمراجعة<input id="file" type="file" accept="application/json,.json" /></label>
      <button id="sample">عرض بيانات العينة</button>
      <button id="clear">مسح</button>
    </div>
    <section id="dashboard" class="grid"></section>
  </main>
<script id="embedded-data" type="application/json">__DATA__</script>
<script>
const embedded = JSON.parse(document.getElementById('embedded-data').textContent || '{}');
const dash = document.getElementById('dashboard');
function esc(v) { return String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
function artifactRoot(data) { return data.artifacts ? data : { artifacts: data, counts: data.counts || {} }; }
function render(data) {
  const root = artifactRoot(data || {});
  const a = root.artifacts || {};
  const profile = a.profile || data.profile || {};
  const policy = a.policy || data.policy || {};
  const counts = root.counts || data.counts || {};
  const warnings = data.warnings || [];
  const recs = data.top_recommendations || (a.efficiency_reports && a.efficiency_reports[0] && a.efficiency_reports[0].recommendations) || [];
  const encryptedCount = data.encrypted_report_count ?? counts.encrypted_reports ?? 0;
  const digest = data.digest_checksum || (a.evidence_digests && a.evidence_digests[0] && a.evidence_digests[0].stable_checksum) || 'غير متوفر';
  const status = data.status || ((a.quality_gate && a.quality_gate.passed) ? 'quality-gate:passed' : 'review-ready');
  const rows = Object.entries(counts).sort().map(([k,v]) => `<tr><td>${esc(k)}</td><td>${esc(v)}</td></tr>`).join('');
  dash.innerHTML = `
    <div class="card"><div class="k">Workflow</div><div class="v">${esc(root.workflow_id || data.workflow_id || 'unknown')}</div></div>
    <div class="card"><div class="k">Status</div><div class="v ${status.includes('attention')?'warn':'ok'}">${esc(status)}</div></div>
    <div class="card"><div class="k">Encrypted reports</div><div class="v">${esc(encryptedCount)}</div></div>
    <div class="card"><div class="k">Risk</div><div class="v">${esc(data.risk || profile.risk || 'unknown')}</div></div>
    <div class="card"><div class="k">Policy</div><div class="v">${esc(data.policy_name || policy.name || 'unknown')}</div></div>
    <div class="card"><div class="k">Runtime mode</div><div class="v">${esc(data.runtime_mode || policy.runtime_mode || 'unknown')}</div></div>
    <div class="card wide"><div class="k">Digest checksum</div><div class="v" style="font-size:15px">${esc(digest)}</div></div>
    <div class="card"><div class="k">Schema</div><div class="v" style="font-size:17px">${esc(root.schema_version || data.schema_version || 'snapshot')}</div></div>
    <div class="card wide"><div class="k">Recommendations</div>${(recs.length?recs:['لا توجد توصيات إضافية']).map(x=>`<span class="pill">${esc(x)}</span>`).join('')}</div>
    <div class="card"><div class="k">Warnings</div>${(warnings.length?warnings:['لا توجد تحذيرات']).map(x=>`<span class="pill">${esc(x)}</span>`).join('')}</div>
    <div class="card full"><div class="k">Evidence counts</div><table><thead><tr><th>Artifact</th><th>Count</th></tr></thead><tbody>${rows || '<tr><td>none</td><td>0</td></tr>'}</tbody></table></div>
    <div class="card full"><div class="k">Raw loaded JSON</div><pre>${esc(JSON.stringify(data, null, 2))}</pre></div>`;
}
const demo = {workflow_id:'wf_demo', status:'review-ready', risk:'medium', policy_name:'BalancedPolicy', runtime_mode:'recommend', counts:{encrypted_reports:1, checkpoints:3, runtime_commands:2}, encrypted_report_count:1, top_recommendations:['keep reports encrypted','review digest before full evidence'], warnings:[]};
document.getElementById('sample').onclick = () => render(embedded && Object.keys(embedded).length ? embedded : demo);
document.getElementById('clear').onclick = () => dash.innerHTML = '';
document.getElementById('file').addEventListener('change', async e => { const file=e.target.files[0]; if(!file) return; render(JSON.parse(await file.text())); });
render(embedded && Object.keys(embedded).length ? embedded : demo);
</script>
</body>
</html>"""


def build_adaptive_dashboard_html(snapshot: Any | None = None) -> str:
    data = _safe(snapshot) if snapshot is not None else {}
    payload = json.dumps(data, ensure_ascii=False, sort_keys=True)
    return _HTML_TEMPLATE.replace("__DATA__", payload)


def write_adaptive_dashboard_html(snapshot: Any | None, path: str | Path) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(build_adaptive_dashboard_html(snapshot), encoding="utf-8")
    return target
