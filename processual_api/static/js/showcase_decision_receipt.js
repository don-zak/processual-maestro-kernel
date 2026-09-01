(function installMaestroDecisionReceipt() {
  function addStyles() {
    if (document.getElementById('maestro-decision-receipt-style')) return;
    const style = document.createElement('style');
    style.id = 'maestro-decision-receipt-style';
    style.textContent = `
      .mdr-card{display:none;margin-top:12px;padding:12px;border:1px solid rgba(96,165,250,.28);border-radius:10px;background:rgba(96,165,250,.045)}
      .mdr-card.visible{display:block;animation:mdr-in .28s ease both}
      @keyframes mdr-in{from{opacity:0;transform:translateY(5px)}to{opacity:1;transform:translateY(0)}}
      .mdr-head{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:9px}
      .mdr-title{font-family:'Space Mono',monospace;font-size:10px;font-weight:700;color:#93c5fd;letter-spacing:.05em}
      .mdr-mode{font-family:'DM Mono',monospace;font-size:8px;color:var(--ghost);letter-spacing:.08em}
      .mdr-grid{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:7px}
      .mdr-item{padding:8px;border:1px solid var(--rim);border-radius:8px;background:rgba(8,11,15,.42);min-width:0}
      .mdr-label{display:block;font-family:'DM Mono',monospace;font-size:7px;color:var(--ghost);text-transform:uppercase;letter-spacing:.08em;margin-bottom:4px}
      .mdr-value{display:block;font-family:'DM Mono',monospace;font-size:9px;color:var(--bright);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
      .mdr-value.ok{color:var(--ok)} .mdr-value.warn{color:var(--warn)} .mdr-value.stop{color:var(--error)}
      .mdr-foot{margin-top:8px;font-family:'DM Mono',monospace;font-size:8px;color:var(--ghost);line-height:1.5}
      @media(max-width:980px){.mdr-grid{grid-template-columns:repeat(3,1fr)}}
      @media(max-width:560px){.mdr-grid{grid-template-columns:repeat(2,1fr)}}
    `;
    document.head.appendChild(style);
  }

  function receiptState(decision, status) {
    if (decision === 'CONTROL' && status.includes('Approval recorded')) {
      return { approval: 'Recorded', approvalClass: 'ok', outcome: 'Governed execution · evidence retained', outcomeClass: 'ok' };
    }
    if (decision === 'REPAIR' && status.includes('Qualified fallback executed')) {
      return { approval: 'Not required', approvalClass: '', outcome: 'Fallback executed · evidence retained', outcomeClass: 'warn' };
    }
    if (decision === 'STOP' && status.includes('Fail closed')) {
      return { approval: 'Not applicable', approvalClass: '', outcome: 'Execution denied', outcomeClass: 'stop' };
    }
    return null;
  }

  function addReceipt(journey) {
    if (journey.querySelector('[data-mdr="receipt"]')) return;
    const card = document.createElement('div');
    card.className = 'mdr-card';
    card.dataset.mdr = 'receipt';
    card.innerHTML = `
      <div class="mdr-head"><div class="mdr-title">DECISION RECEIPT</div><div class="mdr-mode">DEMO RECEIPT · synthetic evidence view</div></div>
      <div class="mdr-grid">
        <div class="mdr-item"><span class="mdr-label">Actor</span><span class="mdr-value">Demo operator</span></div>
        <div class="mdr-item"><span class="mdr-label">Authority</span><span class="mdr-value">Governed scope</span></div>
        <div class="mdr-item"><span class="mdr-label">Decision</span><span class="mdr-value" data-mdr-decision>—</span></div>
        <div class="mdr-item"><span class="mdr-label">Approval</span><span class="mdr-value" data-mdr-approval>—</span></div>
        <div class="mdr-item"><span class="mdr-label">Outcome</span><span class="mdr-value" data-mdr-outcome>—</span></div>
        <div class="mdr-item"><span class="mdr-label">Raw secret</span><span class="mdr-value ok">Not included</span></div>
      </div>
      <div class="mdr-foot">The receipt visualizes the evidence contract used by the showcase. It is not a live production audit record.</div>`;

    const result = journey.querySelector('.mdj-result');
    if (result && result.nextSibling) journey.insertBefore(card, result.nextSibling);
    else journey.appendChild(card);

    const decisionNode = journey.querySelector('[data-mdj-decision]');
    const statusNode = journey.querySelector('[data-mdj-status]');
    if (!decisionNode || !statusNode) return;

    const update = () => {
      const decision = (decisionNode.textContent || '').trim();
      const status = (statusNode.textContent || '').trim();
      const state = receiptState(decision, status);
      if (!state) {
        card.classList.remove('visible');
        return;
      }
      const receiptDecision = card.querySelector('[data-mdr-decision]');
      receiptDecision.textContent = decision;
      receiptDecision.className = `mdr-value ${decision === 'STOP' ? 'stop' : decision === 'REPAIR' ? 'warn' : 'ok'}`;
      const approval = card.querySelector('[data-mdr-approval]');
      approval.textContent = state.approval;
      approval.className = `mdr-value ${state.approvalClass}`;
      const outcome = card.querySelector('[data-mdr-outcome]');
      outcome.textContent = state.outcome;
      outcome.className = `mdr-value ${state.outcomeClass}`;
      card.classList.add('visible');
    };

    const observer = new MutationObserver(update);
    observer.observe(decisionNode, { childList: true, subtree: true, characterData: true });
    observer.observe(statusNode, { childList: true, subtree: true, characterData: true });
    update();
  }

  function install() {
    addStyles();
    const journey = document.querySelector('[data-mdj="journey"]');
    if (journey) addReceipt(journey);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', install, { once: true });
  else install();
  setTimeout(install, 450);
  setTimeout(install, 900);
})();