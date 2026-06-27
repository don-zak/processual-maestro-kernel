const GOVERNOR_ADAPTER = (() => {
  async function evaluate(data) {
    const payload = { answer: data.answer, language: data.language || 'en' };
    if (data.client_query) {
      payload.client_query = data.client_query;
    }
    if (data.compatibility !== undefined) {
      payload.compatibility = data.compatibility;
      payload.coherence = data.coherence;
      payload.structural_support = data.structural_support;
      payload.usefulness = data.usefulness;
      payload.complexity = data.complexity;
      payload.fatigue = data.fatigue;
      payload.shock = data.shock;
      payload.lift = data.lift;
      payload.novelty = data.novelty;
      payload.no_answer = data.no_answer;
      payload.hallucination = data.hallucination;
      payload.constraint_failure = data.constraint_failure;
      payload.speed = data.speed || 0.5;
    }
    return CLIENT.post('/cgt/govern', payload);
  }

  async function batch(answers) {
    return CLIENT.post('/cgt/govern/batch', { answers });
  }

  async function status() {
    return CLIENT.get('/cgt/govern/status');
  }

  async function toggle(enabled) {
    return CLIENT.post('/cgt/govern/toggle', { enabled });
  }

  async function reports() {
    return CLIENT.get('/cgt/govern/reports');
  }

  async function repair(answer, policy, language) {
    return CLIENT.post('/cgt/govern/repair', { answer, policy, language: language || 'en' });
  }

  async function evaluateWithPdf(data) {
    return CLIENT.post('/cgt/govern/report', data);
  }

  async function reportsPdf(lang) {
    return CLIENT.get('/cgt/govern/reports/pdf?lang=' + (lang || 'en'));
  }

  async function reportPdfById(evalId, lang) {
    return CLIENT.get('/cgt/govern/reports/' + evalId + '/pdf?lang=' + (lang || 'en'));
  }

  return { evaluate, batch, status, toggle, reports, repair, evaluateWithPdf, reportsPdf, reportPdfById };
})();
