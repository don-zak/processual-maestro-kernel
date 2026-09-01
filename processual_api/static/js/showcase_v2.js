(function installMaestroShowcaseV2() {
  const CONTACT_EMAIL = 'contact@zaxam.net';

  function installStyle() {
    if (document.getElementById('maestro-showcase-v2-style')) return;
    const style = document.createElement('style');
    style.id = 'maestro-showcase-v2-style';
    style.textContent = `
      .msv2-hero{position:relative;overflow:hidden;margin:0 0 var(--s-4);padding:24px;border:1px solid rgba(245,166,35,.28);border-radius:16px;background:radial-gradient(circle at 82% 18%,rgba(245,166,35,.11),transparent 34%),linear-gradient(135deg,rgba(17,22,32,.96),rgba(11,15,23,.9));box-shadow:inset 0 1px 0 rgba(255,255,255,.025)}
      .msv2-hero::after{content:'';position:absolute;right:-35px;top:-45px;width:170px;height:170px;border:1px solid rgba(245,166,35,.12);transform:rotate(30deg);border-radius:30px;pointer-events:none}
      .msv2-eyebrow{font-family:'DM Mono',monospace;font-size:9px;letter-spacing:.14em;color:var(--amber);text-transform:uppercase;margin-bottom:9px}
      .msv2-hero h1{max-width:760px;margin:0;color:var(--bright);font-family:'Syne',sans-serif;font-size:clamp(26px,3vw,42px);line-height:1.04;letter-spacing:-.035em}
      .msv2-hero h1 span{color:var(--amber)}
      .msv2-hero-copy{max-width:780px;margin:12px 0 0;color:var(--soft);font-family:'DM Mono',monospace;font-size:11px;line-height:1.75}
      .msv2-proof-modes{display:flex;flex-wrap:wrap;gap:8px;margin-top:16px}
      .msv2-proof-mode{display:inline-flex;align-items:center;gap:7px;padding:7px 9px;border:1px solid var(--rim);border-radius:8px;background:rgba(8,11,15,.54);font-family:'DM Mono',monospace;font-size:9px;letter-spacing:.06em;color:var(--soft)}
      .msv2-proof-mode b{font-weight:600;color:var(--bright)}
      .msv2-proof-dot{width:6px;height:6px;border-radius:50%;background:var(--amber);box-shadow:0 0 8px rgba(245,166,35,.45)}
      .msv2-proof-mode.recorded .msv2-proof-dot{background:#60a5fa;box-shadow:0 0 8px rgba(96,165,250,.4)}
      .msv2-proof-mode.qualified .msv2-proof-dot{background:var(--ok);box-shadow:0 0 8px rgba(34,211,160,.4)}
      .msv2-hero-actions{display:flex;flex-wrap:wrap;gap:8px;margin-top:16px}
      .msv2-hero-action{border:1px solid rgba(245,166,35,.32);border-radius:8px;padding:8px 11px;background:rgba(245,166,35,.07);color:var(--amber);font-family:'DM Mono',monospace;font-size:9px;letter-spacing:.04em;cursor:pointer}
      .msv2-hero-action.secondary{border-color:var(--rim);background:rgba(17,22,32,.58);color:var(--soft)}
      .msv2-hero-action:hover{filter:brightness(1.12)}
      .msv2-strip{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:0 0 var(--s-4);padding:12px 14px;border:1px solid rgba(245,166,35,.24);border-radius:12px;background:rgba(245,166,35,.045)}
      .msv2-step{font-family:'DM Mono',monospace;font-size:10px;color:var(--soft);padding:5px 8px;border:1px solid var(--rim);border-radius:999px;background:rgba(17,22,32,.72)}
      .msv2-step::before{content:'✓';margin-right:5px;color:var(--ok);font-size:9px}
      .msv2-arrow{color:var(--amber);font-size:11px}
      .msv2-badge{display:inline-flex;align-items:center;gap:7px;padding:6px 10px;border:1px solid rgba(74,174,245,.35);border-radius:999px;background:rgba(74,174,245,.08);color:#93c5fd;font-family:'DM Mono',monospace;font-size:10px;font-weight:600;letter-spacing:.06em}
      .msv2-decision-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin:12px 0 var(--s-4)}
      .msv2-decision{position:relative;overflow:hidden;padding:15px;border:1px solid var(--rim);border-radius:12px;background:rgba(17,22,32,.72)}
      .msv2-decision::after{content:'';position:absolute;left:0;bottom:0;width:100%;height:2px;background:currentColor;opacity:.35}
      .msv2-decision .scenario{display:block;margin-bottom:7px;color:var(--ghost);font-family:'DM Mono',monospace;font-size:8px;letter-spacing:.08em;text-transform:uppercase}
      .msv2-decision strong{display:block;font-family:'Space Mono',monospace;font-size:17px;margin-bottom:5px}
      .msv2-decision p{margin:0;color:var(--soft);font-family:'DM Mono',monospace;font-size:10px;line-height:1.55}
      .msv2-decision .effect{display:block;margin-top:9px;padding-top:8px;border-top:1px solid var(--rim);color:var(--bright);font-family:'DM Mono',monospace;font-size:9px;line-height:1.4}
      .msv2-control{color:var(--amber)} .msv2-repair{color:var(--warn)} .msv2-stop{color:var(--error)}
      .msv2-decision p,.msv2-decision .scenario{color:var(--soft)}
      .msv2-qualification,.msv2-operational-impact{margin:0 0 var(--s-4);padding:14px;border:1px solid rgba(34,211,160,.25);border-radius:12px;background:rgba(34,211,160,.04)}
      .msv2-operational-impact{margin-top:var(--s-3);margin-bottom:0;border-color:rgba(245,166,35,.24);background:rgba(245,166,35,.035)}
      .msv2-impact-row{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin-top:10px}
      .msv2-impact-item{padding:9px 10px;border:1px solid var(--rim);border-radius:8px;font-family:'DM Mono',monospace;font-size:10px;color:var(--soft)}
      .msv2-impact-item strong{display:block;color:var(--bright);font-size:11px;margin-top:3px;word-break:break-word}
      .msv2-gates{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:8px;margin-top:10px}
      .msv2-gate{font-family:'DM Mono',monospace;font-size:10px;padding:8px 10px;border:1px solid var(--rim);border-radius:8px;color:var(--soft)}
      .msv2-gate.ok{color:var(--ok);border-color:rgba(34,211,160,.25)}
      .msv2-gate.pending{color:var(--warn);border-color:rgba(251,191,36,.25)}
      #sidebar-footer .msv2-contact{display:block;margin-top:8px;color:var(--soft);text-decoration:none;font-family:'DM Mono',monospace;font-size:9px;letter-spacing:.04em}
      #sidebar-footer .msv2-contact:hover{color:var(--amber)}
      @media(max-width:820px){.msv2-decision-grid,.msv2-impact-row{grid-template-columns:1fr}.msv2-arrow{display:none}.msv2-hero{padding:18px}.msv2-hero h1{font-size:28px}}
    `;
    document.head.appendChild(style);
  }

  function navigateTo(page) {
    const button = document.querySelector(`.nav-btn[data-page="${page}"]`);
    if (button) button.click();
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

  function addShowcaseHero() {
    const page = document.querySelector('#page-overview > div');
    if (!page || page.querySelector('[data-msv2="hero"]')) return;
    const hero = document.createElement('section');
    hero.className = 'msv2-hero';
    hero.dataset.msv2 = 'hero';
    hero.innerHTML = `
      <div class="msv2-eyebrow">Agentic Operations & Governance Control Plane</div>
      <h1>Capability is not <span>authority.</span></h1>
      <div class="msv2-hero-copy">When an AI agent can perform a real operational action, Maestro determines whether it may act, under which rights and limits, which governance decision applies, and what evidence must remain afterwards.</div>
      <div class="msv2-proof-modes" aria-label="Showcase evidence modes">
        <div class="msv2-proof-mode"><span class="msv2-proof-dot"></span><b>DEMO UI</b><span>deterministic synthetic interaction</span></div>
        <div class="msv2-proof-mode recorded"><span class="msv2-proof-dot"></span><b>RECORDED EVIDENCE</b><span>qualified governance outcomes</span></div>
        <div class="msv2-proof-mode qualified"><span class="msv2-proof-dot"></span><b>TECHNICAL QUALIFICATION</b><span>CI and integrity gates</span></div>
      </div>
      <div class="msv2-hero-actions">
        <button type="button" class="msv2-hero-action" data-msv2-nav="governance">View governed outcomes →</button>
        <button type="button" class="msv2-hero-action secondary" data-msv2-nav="reports">View qualification evidence →</button>
      </div>`;
    page.insertBefore(hero, page.firstChild);
    hero.querySelectorAll('[data-msv2-nav]').forEach((button) => {
      button.addEventListener('click', () => navigateTo(button.dataset.msv2Nav));
    });
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
    const hero = page.querySelector('[data-msv2="hero"]');
    if (hero && hero.nextSibling) page.insertBefore(wrap, hero.nextSibling);
    else page.appendChild(wrap);
  }

  function addGovernanceEvidence() {
    const page = document.querySelector('#page-governance > div');
    if (!page || page.querySelector('[data-msv2="recorded-evidence"]')) return;
    const evidence = document.createElement('div');
    evidence.dataset.msv2 = 'recorded-evidence';
    evidence.innerHTML = `
      <div class="msv2-badge">● RECORDED QUALIFICATION EVIDENCE</div>
      <div class="msv2-decision-grid" aria-label="Governance decision postures">
        <div class="msv2-decision msv2-control"><span class="scenario">SLA incident governance</span><strong>CONTROL</strong><p>The operation is admissible only with an additional control or required human approval.</p><span class="effect">Effect: execution pauses at the approval boundary; the decision remains auditable.</span></div>
        <div class="msv2-decision msv2-repair"><span class="scenario">Provider degradation recovery</span><strong>REPAIR</strong><p>The primary route degrades, so Maestro selects a qualified fallback without expanding authority.</p><span class="effect">Effect: recovery stays inside the prepared runtime and policy boundary.</span></div>
        <div class="msv2-decision msv2-stop"><span class="scenario">Sensitive configuration change</span><strong>STOP</strong><p>A required policy condition is not satisfied, such as an operation outside its approved window.</p><span class="effect">Effect: fail closed; no execution authority is granted.</span></div>
      </div>`;
    page.insertBefore(evidence, page.firstChild);
  }

  function textOf(id) {
    return (document.getElementById(id)?.textContent || '—').trim() || '—';
  }

  function addOperationalImpactCue() {
    const host = document.getElementById('set-usage-summary-card');
    if (!host || host.querySelector('[data-msv2="operational-impact"]')) return;
    const card = document.createElement('div');
    card.className = 'msv2-operational-impact';
    card.dataset.msv2 = 'operational-impact';
    card.innerHTML = `
      <div class="sec-hdr"><div><div class="sh-title">Operational Admission Impact</div><div class="sh-sub">Commercial rights and quota are execution inputs, not billing-only metadata</div></div></div>
      <div class="msv2-impact-row">
        <div class="msv2-impact-item">Quota used<strong data-msv2-impact="used">—</strong></div>
        <div class="msv2-impact-item">Quota remaining<strong data-msv2-impact="remaining">—</strong></div>
        <div class="msv2-impact-item">Latest admission status<strong data-msv2-impact="status">—</strong></div>
      </div>
      <div class="font-data text-muted" style="font-size:10px;margin-top:9px">When policy requires Human Approval, that approval remains a separate governed step and is retained as auditable evidence.</div>`;
    host.appendChild(card);

    const update = () => {
      card.querySelector('[data-msv2-impact="used"]').textContent = textOf('set-usage-quota-used');
      card.querySelector('[data-msv2-impact="remaining"]').textContent = textOf('set-usage-quota-remaining');
      card.querySelector('[data-msv2-impact="status"]').textContent = textOf('set-usage-latest-status');
    };
    update();
    const observed = ['set-usage-quota-used', 'set-usage-quota-remaining', 'set-usage-latest-status']
      .map((id) => document.getElementById(id)).filter(Boolean);
    if (observed.length) {
      const observer = new MutationObserver(update);
      observed.forEach((node) => observer.observe(node, { childList: true, subtree: true, characterData: true }));
    }
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
    addShowcaseHero();
    addOverviewPath();
    addGovernanceEvidence();
    addOperationalImpactCue();
    addQualificationEvidence();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', install, { once: true });
  } else {
    install();
  }
  setTimeout(install, 250);
})();
