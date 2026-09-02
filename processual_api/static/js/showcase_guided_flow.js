(function installMaestroGuidedFlow() {
  const STAGES = [
    {
      id: 'overview',
      page: 'overview',
      title: '01 · Problem → Authority',
      copy: 'Frame the enterprise problem, then show that capability is not authority.',
      target: '[data-msv2="hero"]',
    },
    {
      id: 'decision',
      page: 'overview',
      title: '02 · Decision Journey',
      copy: 'Run CONTROL first. The path must stop at Human Approval, then cross governed Execution before Evidence.',
      target: '[data-mdj="journey"]',
    },
    {
      id: 'governance',
      page: 'governance',
      title: '03 · Governed Outcomes',
      copy: 'Compare CONTROL, REPAIR, and STOP as distinct governed outcomes.',
      target: '[data-msv2="recorded-evidence"]',
    },
    {
      id: 'evidence',
      page: 'reports',
      title: '04 · Qualification Evidence',
      copy: 'Close with technical qualification and keep live owned HTTPS proof visibly separate.',
      target: '[data-msv2="qualification"]',
    },
  ];

  let currentIndex = 0;
  let active = false;

  function addStyles() {
    if (document.getElementById('maestro-guided-flow-style')) return;
    const style = document.createElement('style');
    style.id = 'maestro-guided-flow-style';
    style.textContent = `
      .mgf-launch{position:fixed;right:22px;bottom:22px;z-index:90;border:1px solid rgba(245,166,35,.42);border-radius:999px;padding:9px 13px;background:rgba(10,14,21,.92);backdrop-filter:blur(12px);color:var(--amber);font-family:'DM Mono',monospace;font-size:9px;letter-spacing:.05em;cursor:pointer;box-shadow:0 10px 30px rgba(0,0,0,.3)}
      .mgf-launch:hover{border-color:var(--amber);box-shadow:0 10px 34px rgba(245,166,35,.12)}
      .mgf-panel{position:fixed;right:22px;bottom:22px;z-index:91;width:min(360px,calc(100vw - 44px));border:1px solid rgba(245,166,35,.34);border-radius:14px;padding:14px;background:rgba(10,14,21,.96);backdrop-filter:blur(16px);box-shadow:0 16px 42px rgba(0,0,0,.42);display:none}
      .mgf-panel.active{display:block}
      .mgf-kicker{font-family:'DM Mono',monospace;font-size:8px;letter-spacing:.12em;color:var(--amber);text-transform:uppercase;margin-bottom:6px}
      .mgf-title{font-family:'Syne',sans-serif;font-size:15px;font-weight:700;color:var(--bright);line-height:1.25}
      .mgf-copy{margin-top:6px;font-family:'DM Mono',monospace;font-size:9px;color:var(--soft);line-height:1.55}
      .mgf-progress{display:flex;gap:5px;margin:11px 0}
      .mgf-dot{height:3px;flex:1;border-radius:999px;background:var(--rim);transition:.2s ease}
      .mgf-dot.done{background:var(--ok)} .mgf-dot.active{background:var(--amber);box-shadow:0 0 9px rgba(245,166,35,.35)}
      .mgf-actions{display:flex;align-items:center;gap:7px}
      .mgf-btn{border:1px solid var(--rim);border-radius:8px;padding:7px 9px;background:transparent;color:var(--soft);font-family:'DM Mono',monospace;font-size:8px;cursor:pointer}
      .mgf-btn.primary{margin-left:auto;border-color:rgba(245,166,35,.38);background:rgba(245,166,35,.08);color:var(--amber)}
      .mgf-btn:disabled{opacity:.35;cursor:default}
      .mgf-stage-focus{outline:1px solid rgba(245,166,35,.38)!important;outline-offset:4px;box-shadow:0 0 0 7px rgba(245,166,35,.03),0 0 26px rgba(245,166,35,.08)!important;transition:outline-color .25s ease,box-shadow .25s ease}
      @media(max-width:650px){.mgf-launch,.mgf-panel{right:12px;bottom:12px}.mgf-panel{width:calc(100vw - 24px)}}
      @media(prefers-reduced-motion:reduce){.mgf-dot,.mgf-stage-focus{transition:none}}
    `;
    document.head.appendChild(style);
  }

  function navigateTo(page) {
    const button = document.querySelector(`.nav-btn[data-page="${page}"]`);
    if (button && !button.classList.contains('active')) button.click();
  }

  function clearFocus() {
    document.querySelectorAll('.mgf-stage-focus').forEach((node) => node.classList.remove('mgf-stage-focus'));
  }

  function focusCurrentStage(panel) {
    const stage = STAGES[currentIndex];
    clearFocus();
    navigateTo(stage.page);

    window.setTimeout(() => {
      const target = document.querySelector(stage.target);
      if (target) {
        target.classList.add('mgf-stage-focus');
        target.scrollIntoView({ behavior: 'smooth', block: 'start' });
      }
    }, 120);

    panel.querySelector('[data-mgf-title]').textContent = stage.title;
    panel.querySelector('[data-mgf-copy]').textContent = stage.copy;
    panel.querySelector('[data-mgf-back]').disabled = currentIndex === 0;
    panel.querySelector('[data-mgf-next]').textContent = currentIndex === STAGES.length - 1 ? 'Finish' : 'Next →';
    panel.querySelectorAll('[data-mgf-dot]').forEach((dot, index) => {
      dot.classList.toggle('done', index < currentIndex);
      dot.classList.toggle('active', index === currentIndex);
    });
  }

  function start(panel, launch) {
    active = true;
    currentIndex = 0;
    launch.style.display = 'none';
    panel.classList.add('active');
    focusCurrentStage(panel);
  }

  function exit(panel, launch) {
    active = false;
    clearFocus();
    panel.classList.remove('active');
    launch.style.display = 'block';
  }

  function addController() {
    if (document.querySelector('[data-mgf="controller"]')) return;

    const launch = document.createElement('button');
    launch.type = 'button';
    launch.className = 'mgf-launch';
    launch.dataset.mgf = 'controller';
    launch.textContent = 'Start guided showcase';

    const panel = document.createElement('aside');
    panel.className = 'mgf-panel';
    panel.setAttribute('aria-live', 'polite');
    panel.innerHTML = `
      <div class="mgf-kicker">Presenter guide · manual control</div>
      <div class="mgf-title" data-mgf-title>${STAGES[0].title}</div>
      <div class="mgf-copy" data-mgf-copy>${STAGES[0].copy}</div>
      <div class="mgf-progress">${STAGES.map((_, index) => `<span class="mgf-dot${index === 0 ? ' active' : ''}" data-mgf-dot></span>`).join('')}</div>
      <div class="mgf-actions">
        <button type="button" class="mgf-btn" data-mgf-exit>Exit</button>
        <button type="button" class="mgf-btn" data-mgf-back disabled>← Back</button>
        <button type="button" class="mgf-btn primary" data-mgf-next>Next →</button>
      </div>`;

    document.body.appendChild(launch);
    document.body.appendChild(panel);

    launch.addEventListener('click', () => start(panel, launch));
    panel.querySelector('[data-mgf-exit]').addEventListener('click', () => exit(panel, launch));
    panel.querySelector('[data-mgf-back]').addEventListener('click', () => {
      if (!active || currentIndex === 0) return;
      currentIndex -= 1;
      focusCurrentStage(panel);
    });
    panel.querySelector('[data-mgf-next]').addEventListener('click', () => {
      if (!active) return;
      if (currentIndex === STAGES.length - 1) {
        exit(panel, launch);
        return;
      }
      currentIndex += 1;
      focusCurrentStage(panel);
    });
  }

  function install() {
    addStyles();
    addController();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', install, { once: true });
  else install();
  setTimeout(install, 450);
})();