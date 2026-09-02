(function installMaestroCinematicTransitions() {
  let observerInstalled = false;

  function addStyles() {
    if (document.getElementById('maestro-cinematic-transition-style')) return;
    const style = document.createElement('style');
    style.id = 'maestro-cinematic-transition-style';
    style.textContent = `
      body.mct-guided-active #topbar{opacity:.72;transition:opacity .28s ease}
      body.mct-guided-active #sidebar{filter:saturate(.8);transition:filter .28s ease}
      body.mct-guided-active .page.active{animation:mct-page-enter .34s cubic-bezier(.22,.8,.32,1)}
      body.mct-guided-active .mgf-stage-focus{position:relative;isolation:isolate}
      body.mct-guided-active .mgf-stage-focus::before{content:'';position:absolute;inset:-7px;z-index:-1;border-radius:inherit;background:radial-gradient(circle at 50% 0%,rgba(245,166,35,.10),transparent 58%);pointer-events:none;animation:mct-focus-breathe 2.6s ease-in-out infinite}
      body.mct-guided-active [data-msv2="hero"].mgf-stage-focus{animation:mct-hero-reveal .48s cubic-bezier(.2,.8,.25,1)}
      body.mct-guided-active [data-mdj="journey"].mgf-stage-focus{animation:mct-stage-rise .38s cubic-bezier(.2,.8,.25,1)}
      body.mct-guided-active [data-msv2="recorded-evidence"].mgf-stage-focus,
      body.mct-guided-active [data-msv2="qualification"].mgf-stage-focus{animation:mct-stage-rise .38s cubic-bezier(.2,.8,.25,1)}
      .mct-stage-label{position:fixed;left:50%;top:76px;z-index:92;transform:translate(-50%,-8px);opacity:0;pointer-events:none;padding:6px 10px;border:1px solid rgba(245,166,35,.24);border-radius:999px;background:rgba(8,11,15,.86);backdrop-filter:blur(10px);font-family:'DM Mono',monospace;font-size:8px;letter-spacing:.1em;text-transform:uppercase;color:var(--amber);transition:opacity .22s ease,transform .22s ease}
      .mct-stage-label.visible{opacity:1;transform:translate(-50%,0)}
      @keyframes mct-page-enter{from{opacity:.7;transform:translateY(5px)}to{opacity:1;transform:translateY(0)}}
      @keyframes mct-hero-reveal{from{opacity:.72;transform:translateY(9px) scale(.993)}to{opacity:1;transform:translateY(0) scale(1)}}
      @keyframes mct-stage-rise{from{opacity:.78;transform:translateY(7px)}to{opacity:1;transform:translateY(0)}}
      @keyframes mct-focus-breathe{0%,100%{opacity:.45}50%{opacity:1}}
      @media(prefers-reduced-motion:reduce){
        body.mct-guided-active .page.active,
        body.mct-guided-active [data-msv2="hero"].mgf-stage-focus,
        body.mct-guided-active [data-mdj="journey"].mgf-stage-focus,
        body.mct-guided-active [data-msv2="recorded-evidence"].mgf-stage-focus,
        body.mct-guided-active [data-msv2="qualification"].mgf-stage-focus,
        body.mct-guided-active .mgf-stage-focus::before{animation:none!important}
        .mct-stage-label{transition:none}
      }
    `;
    document.head.appendChild(style);
  }

  function addStageLabel() {
    let label = document.querySelector('[data-mct-stage-label]');
    if (label) return label;
    label = document.createElement('div');
    label.className = 'mct-stage-label';
    label.dataset.mctStageLabel = 'true';
    document.body.appendChild(label);
    return label;
  }

  function syncGuidedState(label) {
    const panel = document.querySelector('.mgf-panel');
    const isActive = Boolean(panel && panel.classList.contains('active'));
    document.body.classList.toggle('mct-guided-active', isActive);

    if (!isActive) {
      label.classList.remove('visible');
      label.textContent = '';
      return;
    }

    const title = panel.querySelector('[data-mgf-title]')?.textContent?.trim() || '';
    label.textContent = title;
    label.classList.toggle('visible', Boolean(title));
  }

  function observeGuidedFlow() {
    if (observerInstalled) return true;
    const label = addStageLabel();
    const panel = document.querySelector('.mgf-panel');
    if (!panel) return false;

    syncGuidedState(label);
    const observer = new MutationObserver(() => syncGuidedState(label));
    observer.observe(panel, {
      attributes: true,
      attributeFilter: ['class'],
      childList: true,
      subtree: true,
      characterData: true,
    });
    observerInstalled = true;
    return true;
  }

  function install() {
    addStyles();
    if (observeGuidedFlow()) return;
    window.setTimeout(observeGuidedFlow, 260);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', install, { once: true });
  else install();
  setTimeout(install, 520);
})();
