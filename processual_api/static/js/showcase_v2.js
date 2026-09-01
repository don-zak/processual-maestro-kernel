(function installMaestroShowcaseV2() {
  const CONTACT_EMAIL = 'contact@zaxam.net';

  function installStyle() {
    if (document.getElementById('maestro-showcase-v2-style')) return;
    const style = document.createElement('style');
    style.id = 'maestro-showcase-v2-style';
    style.textContent = `
      .msv2-strip{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:0 0 var(--s-4);padding:12px 14px;border:1px solid rgba(245,166,35,.24);border-radius:12px;background:rgba(245,166,35,.045)}
      .msv2-step{font-family:'DM Mono',monospace;font-size:10px;color:var(--soft);padding:5px 8px;border:1px solid var(--rim);border-radius:999px;background:rgba(17,22,32,.72)}
      .msv2-arrow{color:var(--amber);font-size:11px}
      .msv2-badge{display:inline-flex;align-items:center;gap:7px;padding:6px 10px;border:1px solid rgba(74,174,245,.35);border-radius:999px;background:rgba(74,174,245,.08);color:#93c5fd;font-family:'DM Mono',monospace;font-size:10px;font-weight:600;letter-spacing:.06em}
      .msv2-decision-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin:12px 0 var(--s-4)}
      .msv2-decision{padding:14px;border:1px solid var(--rim);border-radius:12px;background:rgba(17,22,32,.72)}
      .msv2-decision strong{display:block;font-family:'Space Mono',monospace;font-size:15px;margin-bottom:5px}
      .msv2-decision p{margin:0;color:var(--soft);font-family:'DM Mono',monospace;font-size:10px;line-height:1.5}
      .msv2-control strong{color:var(--amber)} .msv2-repair strong{color:var(--warn)} .msv2-stop strong{color:var(--error)}
      .msv2-qualification{margin:0 0 var(--s-4);padding:14px;border:1px solid rgba(34,211,160,.25);border-radius:12px;background:rgba(34,211,160,.04)}
      .msv2-gates{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:8px;margin-top:10px}
      .msv2-gate{font-family:'DM Mono',monospace;font-size:10px;padding:8px 10px;border:1px solid var(--rim);border-radius:8px;color:var(--soft)}
      .msv2-gate.ok{color:var(--ok);border-color:rgba(34,211,160,.25)}
      .msv2-gate.pending{color:var(--warn);border-color:rgba(251,191,36,.25)}
      #sidebar-footer .msv2-contact{display:block;margin-top:8px;color:var(--soft);text-decoration:none;font-family:'DM Mono',monospace;font-size:9px;letter-spacing:.04em}
      #sidebar-footer .msv2-contact:hover{color:var(--amber)}
      @media(max-width:820px){.msv2-decision-grid{grid-template-columns:1fr}.msv2-arrow{display:none}}
    `;
    document.head.appendChild(style);
  }

  function addContact() {
    const footer = document.getElementById('sidebar-footer');
    if (!footer) return;
    const version = footer.querySelector('.v');
    if (version && /production/i.test(version.textContent || '')) {
      version.textContent = 'v2.0.0 - CI-qualified demo';
    }
    if (!footer.querySelector('.msv2-contact')) {
      const link = document.createElement('a');
      link.className = 'msv2-contact';
      link.href = 'mailto:' + CONTACT_EMAIL;
      link.textContent = CONTACT_EMAIL;
      footer.appendChild(link);
    }
  }

  function addOverviewPath() {
    const page = document.querySelector('#page-overview > div');
    if (!page || page.querySelector('[data-msv2="governance-path"]')) return;
    const wrap = document.createElement('div');
    wrap.className = 'msv2-strip';
    wrap.dataset.msv2 = 'governance-path';
    const steps = ['Actor', 'Authority', 'Commercial Rights', 'Quota', 'Governance', 'Human Approval', 'Execution', 'Evidence'];
    steps.forEach((step, index) => {
      const pill = document.createElement('span');
      pill.className = 'msv2-step';
      pill.textContent = step;
      wrap.appendChild(pill);
      if (index < steps.length - 1) {
        const arrow = document.createElement('span');
        arrow.className = 'msv2-arrow';
        arrow.textContent = '→';
        wrap.appendChild(arrow);
      }
    });
    page.insertBefore(wrap, page.firstChild);
  }

  function addGovernanceEvidence() {
    const page = document.querySelector('#page-governance > div');
    if (!page || page.querySelector('[data-msv2="recorded-evidence"]')) return;
    const evidence = document.createElement('div');
    evidence.dataset.msv2 = 'recorded-evidence';
    evidence.innerHTML = `
      <div class="msv2-badge">● RECORDED QUALIFICATION EVIDENCE</div>
      <div class="msv2-decision-grid" aria-label="Governance decision postures">
        <div class="msv2-decision msv2-control"><strong>CONTROL</strong><p>Continue only with an additional control or required human approval.</p></div>
        <div class="msv2-decision msv2-repair"><strong>REPAIR</strong><p>Recover through a qualified fallback while preserving governance boundaries.</p></div>
        <div class="msv2-decision msv2-stop"><strong>STOP</strong><p>Fail closed when a required policy condition is not satisfied.</p></div>
      </div>`;
    page.insertBefore(evidence, page.firstChild);
  }

  function addQualificationEvidence() {
    const page = document.querySelector('#page-reports > div');
    if (!page || page.querySelector('[data-msv2="qualification"]')) return;
    const card = document.createElement('div');
    card.className = 'msv2-qualification';
    card.dataset.msv2 = 'qualification';
    card.innerHTML = `
      <div class="sec-hdr"><div><div class="sh-title">Qualification Evidence</div><div class="sh-sub">Code qualification is separate from live external runtime proof</div></div></div>
      <div class="msv2-gates">
        <div class="msv2-gate ok">✓ Public CI</div>
        <div class="msv2-gate ok">✓ Security</div>
        <div class="msv2-gate ok">✓ Deep Integrity</div>
        <div class="msv2-gate ok">✓ Pre-External Readiness</div>
        <div class="msv2-gate ok">✓ SHA-bound qualification</div>
        <div class="msv2-gate pending">○ Live owned HTTPS proof - separate gate</div>
      </div>`;
    page.insertBefore(card, page.firstChild);
  }

  function install() {
    installStyle();
    addContact();
    addOverviewPath();
    addGovernanceEvidence();
    addQualificationEvidence();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', install, { once: true });
  } else {
    install();
  }
  setTimeout(install, 250);
})();
