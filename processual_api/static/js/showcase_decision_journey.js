(function installMaestroDecisionJourney() {
  const STEPS = [
    { id: 'identity', label: 'Identity', detail: 'Actor identity resolved' },
    { id: 'authority', label: 'Authority', detail: 'Execution authority present' },
    { id: 'entitlement', label: 'Entitlement', detail: 'Operational right admitted' },
    { id: 'quota', label: 'Quota', detail: 'Usage remains inside the allowed limit' },
    { id: 'capacity', label: 'Capacity', detail: 'Runtime capacity available' },
    { id: 'governance', label: 'Governance', detail: 'Policy requires an additional control' },
    { id: 'approval', label: 'Human Approval', detail: 'Execution pauses at the human boundary' },
    { id: 'evidence', label: 'Evidence', detail: 'Decision and approval trail retained' },
  ];

  const SCENARIOS = {
    control: {
      eyebrow: 'Scenario 01 · SLA incident governance',
      decision: 'CONTROL',
      decisionClass: 'control',
      reason: 'Human approval required',
      description: 'A governed operational action is admissible, but it cannot cross the approval boundary automatically.',
      stopAt: 'approval',
      finalLabel: 'Approval recorded → evidence retained',
    },
    repair: {
      eyebrow: 'Scenario 02 · Provider degradation recovery',
      decision: 'REPAIR',
      decisionClass: 'repair',
      reason: 'Qualified fallback available',
      description: 'The primary provider degrades. Maestro redirects through a prepared fallback without expanding authority.',
      stopAt: 'governance',
      finalLabel: 'Fallback selected inside policy boundary',
    },
    stop: {
      eyebrow: 'Scenario 03 · Sensitive configuration change',
      decision: 'STOP',
      decisionClass: 'stop',
      reason: 'Outside approved maintenance window',
      description: 'A required policy condition is not satisfied, so execution authority is denied before the external action.',
      stopAt: 'governance',
      finalLabel: 'Fail closed → no execution granted',
    },
  };

  let runToken = 0;
  let activeScenario = 'control';

  function addStyles() {
    if (document.getElementById('maestro-decision-journey-style')) return;
    const style = document.createElement('style');
    style.id = 'maestro-decision-journey-style';
    style.textContent = `
      .mdj-shell{margin:0 0 var(--s-4);padding:18px;border:1px solid rgba(245,166,35,.28);border-radius:14px;background:linear-gradient(180deg,rgba(17,22,32,.94),rgba(10,14,21,.9));overflow:hidden}
      .mdj-head{display:flex;justify-content:space-between;gap:16px;align-items:flex-start;margin-bottom:14px}
      .mdj-eyebrow{font-family:'DM Mono',monospace;font-size:9px;letter-spacing:.12em;text-transform:uppercase;color:var(--amber);margin-bottom:6px}
      .mdj-title{font-family:'Syne',sans-serif;font-weight:700;color:var(--bright);font-size:18px;line-height:1.2}
      .mdj-sub{max-width:720px;margin-top:5px;color:var(--soft);font-family:'DM Mono',monospace;font-size:10px;line-height:1.55}
      .mdj-mode{flex:0 0 auto;padding:5px 8px;border:1px solid rgba(245,166,35,.22);border-radius:999px;color:var(--amber);font-family:'DM Mono',monospace;font-size:8px;letter-spacing:.08em}
      .mdj-scenarios{display:flex;flex-wrap:wrap;gap:7px;margin-bottom:14px}
      .mdj-scenario{border:1px solid var(--rim);border-radius:9px;padding:7px 9px;background:rgba(8,11,15,.44);color:var(--soft);font-family:'DM Mono',monospace;font-size:9px;cursor:pointer;transition:.18s ease}
      .mdj-scenario:hover{border-color:rgba(245,166,35,.34);color:var(--bright)}
      .mdj-scenario.active{border-color:rgba(245,166,35,.48);background:rgba(245,166,35,.08);color:var(--amber)}
      .mdj-track{position:relative;display:grid;grid-template-columns:repeat(8,minmax(82px,1fr));gap:8px;margin-top:8px}
      .mdj-track::before{content:'';position:absolute;left:5%;right:5%;top:22px;height:2px;background:var(--rim);z-index:0}
      .mdj-node{position:relative;z-index:1;min-width:0;padding-top:0;text-align:center}
      .mdj-node-core{width:44px;height:44px;margin:0 auto 8px;border-radius:50%;display:flex;align-items:center;justify-content:center;border:1px solid var(--rim);background:var(--surface-0);color:var(--ghost);font-family:'Space Mono',monospace;font-size:10px;font-weight:700;transition:.22s ease;box-shadow:0 0 0 0 rgba(245,166,35,0)}
      .mdj-node-label{font-family:'DM Mono',monospace;font-size:8px;color:var(--ghost);line-height:1.25;min-height:21px;transition:.22s ease}
      .mdj-node-detail{display:none}
      .mdj-node.done .mdj-node-core{border-color:rgba(34,211,160,.45);background:rgba(34,211,160,.08);color:var(--ok)}
      .mdj-node.done .mdj-node-label{color:var(--soft)}
      .mdj-node.active .mdj-node-core{border-color:var(--amber);color:var(--amber);background:rgba(245,166,35,.11);box-shadow:0 0 0 7px rgba(245,166,35,.055),0 0 20px rgba(245,166,35,.20);transform:scale(1.06)}
      .mdj-node.active .mdj-node-label{color:var(--bright)}
      .mdj-node.blocked .mdj-node-core{border-color:rgba(248,113,113,.48);color:var(--error);background:rgba(248,113,113,.08)}
      .mdj-node.blocked .mdj-node-label{color:var(--error)}
      .mdj-pulse{position:absolute;top:20px;left:4%;height:5px;width:0;border-radius:999px;background:linear-gradient(90deg,var(--amber-dim),var(--amber));box-shadow:0 0 14px rgba(245,166,35,.42);z-index:0;transition:width .42s ease}
      .mdj-result{display:grid;grid-template-columns:minmax(150px,.7fr) minmax(0,1.3fr);gap:10px;margin-top:16px}
      .mdj-decision,.mdj-reason{border:1px solid var(--rim);border-radius:10px;padding:12px;background:rgba(8,11,15,.44)}
      .mdj-decision-label,.mdj-reason-label{font-family:'DM Mono',monospace;font-size:8px;text-transform:uppercase;letter-spacing:.1em;color:var(--ghost);margin-bottom:5px}
      .mdj-decision-value{font-family:'Space Mono',monospace;font-size:20px;font-weight:700;color:var(--ghost)}
      .mdj-decision-value.control{color:var(--amber)} .mdj-decision-value.repair{color:var(--warn)} .mdj-decision-value.stop{color:var(--error)}
      .mdj-reason-value{font-family:'DM Mono',monospace;font-size:10px;color:var(--bright);line-height:1.5}
      .mdj-status{margin-top:8px;font-family:'DM Mono',monospace;font-size:9px;color:var(--soft);min-height:14px}
      .mdj-actions{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px}
      .mdj-run,.mdj-approve,.mdj-reset{border-radius:8px;padding:8px 11px;font-family:'DM Mono',monospace;font-size:9px;cursor:pointer}
      .mdj-run{border:1px solid rgba(245,166,35,.38);background:rgba(245,166,35,.09);color:var(--amber)}
      .mdj-approve{display:none;border:1px solid rgba(34,211,160,.4);background:rgba(34,211,160,.08);color:var(--ok)}
      .mdj-reset{border:1px solid var(--rim);background:transparent;color:var(--soft)}
      .mdj-note{margin-top:10px;color:var(--ghost);font-family:'DM Mono',monospace;font-size:8px;line-height:1.5}
      @media(max-width:1050px){.mdj-track{grid-template-columns:repeat(4,1fr)}.mdj-track::before,.mdj-pulse{display:none}}
      @media(max-width:650px){.mdj-track{grid-template-columns:repeat(2,1fr)}.mdj-result{grid-template-columns:1fr}.mdj-head{flex-direction:column}}
    `;
    document.head.appendChild(style);
  }

  function nodeMarkup(step, index) {
    return `<div class="mdj-node" data-mdj-step="${step.id}">
      <div class="mdj-node-core">${String(index + 1).padStart(2, '0')}</div>
      <div class="mdj-node-label">${step.label}</div>
      <div class="mdj-node-detail">${step.detail}</div>
    </div>`;
  }

  function addJourney() {
    const page = document.querySelector('#page-overview > div');
    if (!page || page.querySelector('[data-mdj="journey"]')) return;
    const journey = document.createElement('section');
    journey.className = 'mdj-shell';
    journey.dataset.mdj = 'journey';
    journey.innerHTML = `
      <div class="mdj-head">
        <div>
          <div class="mdj-eyebrow" data-mdj-eyebrow>${SCENARIOS.control.eyebrow}</div>
          <div class="mdj-title">Governed Decision Journey</div>
          <div class="mdj-sub" data-mdj-description>${SCENARIOS.control.description}</div>
        </div>
        <div class="mdj-mode">DEMO UI · deterministic sequence</div>
      </div>
      <div class="mdj-scenarios" role="tablist" aria-label="Showcase scenarios">
        <button type="button" class="mdj-scenario active" data-mdj-scenario="control">01 · CONTROL</button>
        <button type="button" class="mdj-scenario" data-mdj-scenario="repair">02 · REPAIR</button>
        <button type="button" class="mdj-scenario" data-mdj-scenario="stop">03 · STOP</button>
      </div>
      <div class="mdj-track" aria-label="Identity to evidence decision path">
        <div class="mdj-pulse" data-mdj-pulse></div>
        ${STEPS.map(nodeMarkup).join('')}
      </div>
      <div class="mdj-result">
        <div class="mdj-decision">
          <div class="mdj-decision-label">Governance decision</div>
          <div class="mdj-decision-value" data-mdj-decision>—</div>
        </div>
        <div class="mdj-reason">
          <div class="mdj-reason-label">Decision reason / immediate effect</div>
          <div class="mdj-reason-value" data-mdj-reason>Run the scenario to evaluate the operational boundary.</div>
          <div class="mdj-status" data-mdj-status>Ready.</div>
        </div>
      </div>
      <div class="mdj-actions">
        <button type="button" class="mdj-run" data-mdj-run>Run decision path</button>
        <button type="button" class="mdj-approve" data-mdj-approve>Record human approval</button>
        <button type="button" class="mdj-reset" data-mdj-reset>Reset</button>
      </div>
      <div class="mdj-note">This showcase sequence is deterministic synthetic UI. It demonstrates Maestro's decision model; it does not claim live production execution.</div>`;

    const hero = page.querySelector('[data-msv2="hero"]');
    const overviewPath = page.querySelector('[data-msv2="governance-path"]');
    if (overviewPath && overviewPath.nextSibling) page.insertBefore(journey, overviewPath.nextSibling);
    else if (hero && hero.nextSibling) page.insertBefore(journey, hero.nextSibling);
    else page.insertBefore(journey, page.firstChild);

    bindJourney(journey);
  }

  function resetJourney(journey) {
    runToken += 1;
    journey.querySelectorAll('.mdj-node').forEach((node) => {
      node.classList.remove('done', 'active', 'blocked');
    });
    journey.querySelector('[data-mdj-pulse]').style.width = '0%';
    const decision = journey.querySelector('[data-mdj-decision]');
    decision.textContent = '—';
    decision.className = 'mdj-decision-value';
    journey.querySelector('[data-mdj-reason]').textContent = 'Run the scenario to evaluate the operational boundary.';
    journey.querySelector('[data-mdj-status]').textContent = 'Ready.';
    journey.querySelector('[data-mdj-approve]').style.display = 'none';
  }

  function selectScenario(journey, scenarioId) {
    activeScenario = scenarioId;
    const scenario = SCENARIOS[scenarioId];
    journey.querySelectorAll('[data-mdj-scenario]').forEach((button) => {
      button.classList.toggle('active', button.dataset.mdjScenario === scenarioId);
    });
    journey.querySelector('[data-mdj-eyebrow]').textContent = scenario.eyebrow;
    journey.querySelector('[data-mdj-description]').textContent = scenario.description;
    resetJourney(journey);
  }

  function wait(ms) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  async function runJourney(journey) {
    const token = ++runToken;
    resetVisualStateForRun(journey);
    const scenario = SCENARIOS[activeScenario];
    const stopIndex = STEPS.findIndex((step) => step.id === scenario.stopAt);

    for (let index = 0; index <= stopIndex; index += 1) {
      if (token !== runToken) return;
      const step = STEPS[index];
      const node = journey.querySelector(`[data-mdj-step="${step.id}"]`);
      journey.querySelectorAll('.mdj-node.active').forEach((item) => item.classList.remove('active'));
      node.classList.add('active');
      journey.querySelector('[data-mdj-status]').textContent = step.detail;
      journey.querySelector('[data-mdj-pulse]').style.width = `${Math.min(92, 6 + (index * 12.3))}%`;
      await wait(index === stopIndex ? 620 : 430);
      if (token !== runToken) return;
      if (index < stopIndex) {
        node.classList.remove('active');
        node.classList.add('done');
      }
    }

    const decision = journey.querySelector('[data-mdj-decision]');
    decision.textContent = scenario.decision;
    decision.className = `mdj-decision-value ${scenario.decisionClass}`;
    journey.querySelector('[data-mdj-reason]').textContent = scenario.reason;

    if (activeScenario === 'control') {
      journey.querySelector('[data-mdj-status]').textContent = 'Execution paused. Human approval is required before evidence finalization.';
      journey.querySelector('[data-mdj-approve]').style.display = 'inline-block';
    } else if (activeScenario === 'repair') {
      const governance = journey.querySelector('[data-mdj-step="governance"]');
      governance.classList.remove('active');
      governance.classList.add('done');
      journey.querySelector('[data-mdj-status]').textContent = scenario.finalLabel;
    } else {
      const governance = journey.querySelector('[data-mdj-step="governance"]');
      governance.classList.remove('active');
      governance.classList.add('blocked');
      journey.querySelector('[data-mdj-status]').textContent = scenario.finalLabel;
    }
  }

  function resetVisualStateForRun(journey) {
    runToken += 1;
    journey.querySelectorAll('.mdj-node').forEach((node) => {
      node.classList.remove('done', 'active', 'blocked');
    });
    journey.querySelector('[data-mdj-pulse]').style.width = '0%';
    journey.querySelector('[data-mdj-approve]').style.display = 'none';
    const decision = journey.querySelector('[data-mdj-decision]');
    decision.textContent = 'Evaluating…';
    decision.className = 'mdj-decision-value';
    journey.querySelector('[data-mdj-reason]').textContent = 'Identity and execution conditions are checked before the operation can proceed.';
  }

  async function recordApproval(journey) {
    const token = ++runToken;
    const approval = journey.querySelector('[data-mdj-step="approval"]');
    approval.classList.remove('active');
    approval.classList.add('done');
    journey.querySelector('[data-mdj-status]').textContent = 'Human approval recorded. Finalizing auditable evidence…';
    journey.querySelector('[data-mdj-pulse]').style.width = '92%';
    await wait(520);
    if (token !== runToken) return;
    const evidence = journey.querySelector('[data-mdj-step="evidence"]');
    evidence.classList.add('active');
    await wait(430);
    if (token !== runToken) return;
    evidence.classList.remove('active');
    evidence.classList.add('done');
    journey.querySelector('[data-mdj-pulse]').style.width = '100%';
    journey.querySelector('[data-mdj-status]').textContent = SCENARIOS.control.finalLabel;
    journey.querySelector('[data-mdj-approve]').style.display = 'none';
  }

  function bindJourney(journey) {
    journey.querySelectorAll('[data-mdj-scenario]').forEach((button) => {
      button.addEventListener('click', () => selectScenario(journey, button.dataset.mdjScenario));
    });
    journey.querySelector('[data-mdj-run]').addEventListener('click', () => runJourney(journey));
    journey.querySelector('[data-mdj-approve]').addEventListener('click', () => recordApproval(journey));
    journey.querySelector('[data-mdj-reset]').addEventListener('click', () => resetJourney(journey));
  }

  function install() {
    addStyles();
    addJourney();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', install, { once: true });
  else install();
  setTimeout(install, 350);
})();
