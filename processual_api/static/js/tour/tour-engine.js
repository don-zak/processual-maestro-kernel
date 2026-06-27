/* ─── Tour Engine v1.0 — Interactive Walkthrough ─── */
const TOUR = (() => {
  let _steps = [];
  let _currentStep = 0;
  let _isRunning = false;
  let _lang = 'en';
  let _overlay = null;
  let _tooltip = null;
  let _highlight = null;
  let _helpBtn = null;
  let _arrow = null;
  let _resolvePage = null;

  /* ─── Init — call once at startup ─── */
  function init() {
    addHelpButton();
    const saved = localStorage.getItem('tour_completed');
    const lang = localStorage.getItem('tour_lang') || 'en';
    _lang = lang;
    if (!saved) {
      setTimeout(() => showLangSelector(), 600);
    }
  }

  /* ─── Add ? button to topbar ─── */
  function addHelpButton() {
    const right = document.getElementById('topbar-right');
    if (!right) return;
    _helpBtn = document.createElement('button');
    _helpBtn.id = 'tour-help-btn';
    _helpBtn.textContent = '⍰';
    _helpBtn.title = 'Start tutorial tour';
    _helpBtn.addEventListener('click', () => {
      if (_isRunning) return;
      if (localStorage.getItem('tour_completed')) {
        showToast('Tour restarted', 'info');
      }
      showLangSelector();
    });
    right.insertBefore(_helpBtn, right.firstChild);
  }

  /* ─── Language selector modal ─── */
  function showLangSelector() {
    const modal = document.createElement('div');
    modal.className = 'tour-lang-modal';
    modal.id = 'tour-lang-modal';
    modal.innerHTML = `
      <div class="tour-lang-card">
        <div class="tlc-title">🌐 Choose Tour Language</div>
        <div class="tlc-sub">Select your preferred language for the guided tour.<br>اختر لغتك المفضلة للجولة الإرشادية.</div>
        <div class="tlc-btns">
          <button class="tlc-btn" data-lang="en">🇬🇧 English</button>
          <button class="tlc-btn" data-lang="ar">🇸🇦 العربية</button>
        </div>
        <div style="margin-top:var(--s-5)"><button class="tlc-btn skip-btn" id="tour-lang-skip">Skip tour / تخطي الجولة</button></div>
      </div>`;
    document.body.appendChild(modal);

    modal.querySelectorAll('.tlc-btn[data-lang]').forEach(btn => {
      btn.addEventListener('click', () => {
        const lang = btn.dataset.lang;
        modal.remove();
        start(lang);
      });
    });
    document.getElementById('tour-lang-skip').addEventListener('click', () => {
      modal.remove();
      localStorage.setItem('tour_completed', 'true');
      showToast('Tour skipped', 'info');
    });
  }

  /* ─── Start the tour ─── */
  function start(lang) {
    _lang = lang || _lang;
    _steps = TOUR_STEPS[_lang] || TOUR_STEPS.en;
    _currentStep = parseInt(localStorage.getItem('tour_progress')) || 0;
    if (_currentStep >= _steps.length) _currentStep = 0;
    _isRunning = true;
    localStorage.setItem('tour_completed', 'false');
    localStorage.setItem('tour_lang', _lang);
    renderStep();
  }

  /* ─── Render current step ─── */
  function renderStep() {
    const step = _steps[_currentStep];
    if (!step) { end(); return; }

    cleanup();
    createOverlay();

    // Navigate to page
    if (step.page) {
      const navBtn = document.querySelector('.nav-btn[data-page="' + step.page + '"]');
      if (navBtn) navBtn.click();
    }

    // Wait for page transition, then highlight
    setTimeout(() => {
      if (step.sidebar) {
        const sb = document.querySelector(step.sidebar);
        if (sb) sb.classList.add('tour-nav-active');
      }
      doHighlight(step.target);
      doTooltip(step);
    }, 350);
  }

  /* ─── Overlay ─── */
  function createOverlay() {
    _overlay = document.createElement('div');
    _overlay.className = 'tour-overlay';
    document.body.appendChild(_overlay);
  }

  /* ─── Highlight element ─── */
  function doHighlight(selector) {
    const el = selector ? document.querySelector(selector) : null;
    if (!el) {
      // Fallback: highlight topbar
      const fb = document.getElementById('topbar') || document.getElementById('content');
      if (fb) {
        fb.scrollIntoView({ behavior: 'smooth', block: 'center' });
        _highlight = document.createElement('div');
        _highlight.className = 'tour-highlight';
        const rect = fb.getBoundingClientRect();
        Object.assign(_highlight.style, {
          position: 'fixed', left: rect.left - 4 + 'px', top: rect.top - 4 + 'px',
          width: rect.width + 8 + 'px', height: rect.height + 8 + 'px',
          borderRadius: '6px', pointerEvents: 'none', zIndex: '1001'
        });
        document.body.appendChild(_highlight);
      }
      return;
    }
    el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    _highlight = document.createElement('div');
    _highlight.className = 'tour-highlight';
    const rect = el.getBoundingClientRect();
    const rad = getComputedStyle(el).borderRadius || 'var(--radius-lg)';
    Object.assign(_highlight.style, {
      position: 'fixed', left: rect.left - 4 + 'px', top: rect.top - 4 + 'px',
      width: rect.width + 8 + 'px', height: rect.height + 8 + 'px',
      borderRadius: rad, pointerEvents: 'none', zIndex: '1001'
    });
    document.body.appendChild(_highlight);
  }

  /* ─── Tooltip ─── */
  function doTooltip(step) {
    const total = _steps.length;
    const pos = step.position || 'bottom';
    _tooltip = document.createElement('div');
    _tooltip.className = 'tour-tooltip';
    _tooltip.dataset.position = pos;
    _tooltip.innerHTML = `
      <div class="tt-header">
        <span class="tt-step">${_currentStep + 1}/${total}</span>
        <span class="tt-title">${step.title}</span>
      </div>
      <div class="tt-body">${step.content}</div>
      <div class="tt-progress"><div class="tt-bar" style="width:${((_currentStep + 1) / total) * 100}%"></div></div>
      <div class="tt-actions">
        ${_currentStep > 0 ? '<button class="tt-btn tt-prev" data-action="prev">' + (_lang === 'ar' ? '→ السابق' : '← Previous') + '</button>' : ''}
        <button class="tt-btn tt-skip" data-action="skip">${_lang === 'ar' ? '✕ تخطي' : '✕ Skip'}</button>
        <button class="tt-btn tt-next accent" data-action="next">${_currentStep < total - 1 ? (_lang === 'ar' ? 'التالي →' : 'Next →') : (_lang === 'ar' ? 'إنهاء ✓' : 'Finish ✓')}</button>
      </div>`;
    document.body.appendChild(_tooltip);
    positionTooltip(pos);

    _tooltip.querySelectorAll('[data-action]').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const action = e.currentTarget.dataset.action;
        if (action === 'next') next();
        else if (action === 'prev') prev();
        else if (action === 'skip') skip();
      });
    });
  }

  /* ─── Position tooltip near center of screen ─── */
  function positionTooltip(pos) {
    if (!_tooltip) return;
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    const tw = _tooltip.offsetWidth || 340;
    const th = _tooltip.offsetHeight || 200;
    const pad = 20;

    let x = (vw - tw) / 2;
    let y = (vh - th) / 2;

    if (pos === 'top') y = pad;
    else if (pos === 'bottom') y = vh - th - pad;
    else if (pos === 'left') x = pad;
    else if (pos === 'right') x = vw - tw - pad;

    _tooltip.style.left = Math.max(pad, Math.min(vw - tw - pad, x)) + 'px';
    _tooltip.style.top = Math.max(pad, Math.min(vh - th - pad, y)) + 'px';
  }

  /* ─── Navigation ─── */
  function next() {
    _currentStep++;
    saveProgress();
    if (_currentStep >= _steps.length) {
      end();
    } else {
      renderStep();
    }
  }

  function prev() {
    if (_currentStep > 0) {
      _currentStep--;
      saveProgress();
      renderStep();
    }
  }

  function skip() {
    cleanup();
    _isRunning = false;
    localStorage.setItem('tour_completed', 'true');
    localStorage.removeItem('tour_progress');
    showToast(_lang === 'ar' ? 'تم تخطي الجولة' : 'Tour skipped', 'info');
  }

  function end() {
    cleanup();
    _isRunning = false;
    localStorage.setItem('tour_completed', 'true');
    localStorage.removeItem('tour_progress');
    showToast(_lang === 'ar' ? 'اكتملت الجولة!' : 'Tour completed!', 'success');
  }

  function saveProgress() {
    localStorage.setItem('tour_progress', _currentStep.toString());
  }

  /* ─── Cleanup ─── */
  function cleanup() {
    if (_overlay) { _overlay.remove(); _overlay = null; }
    if (_tooltip) { _tooltip.remove(); _tooltip = null; }
    if (_highlight) { _highlight.remove(); _highlight = null; }
    if (_arrow) { _arrow.remove(); _arrow = null; }
    document.querySelectorAll('.tour-nav-active').forEach(el => el.classList.remove('tour-nav-active'));
  }

  /* ─── Toast helper (standalone, doesn't depend on APP) ─── */
  function showToast(msg, type) {
    type = type || 'info';
    let container = document.getElementById('toast-container');
    if (!container) {
      container = document.createElement('div');
      container.id = 'toast-container';
      container.style.cssText = 'position:fixed;top:var(--s-6);right:var(--s-6);z-index:9999;display:flex;flex-direction:column;gap:var(--s-3);pointer-events:none';
      document.body.appendChild(container);
    }
    const t = document.createElement('div');
    t.className = 'toast ' + type;
    t.innerHTML = '<span>' + msg + '</span>';
    container.appendChild(t);
    setTimeout(() => { if (t.parentElement) t.remove(); }, 3500);
  }

  /* ─── Public API ─── */
  function isFirstVisit() { return !localStorage.getItem('tour_completed'); }
  function isRunning() { return _isRunning; }
  function resume() {
    const p = localStorage.getItem('tour_progress');
    if (p !== null) { _currentStep = parseInt(p); start(_lang); }
    else { showLangSelector(); }
  }

  return { init, start, resume, isFirstVisit, isRunning, skip };
})();
