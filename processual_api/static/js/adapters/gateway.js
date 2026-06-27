const GATEWAY_ADAPTER = (() => {
  async function evaluate(agentId, clientQuery, agentResponse, language) {
    return CLIENT.post('/cgt/govern/gateway/evaluate', {
      agent_id: agentId, client_query: clientQuery,
      agent_response: agentResponse, language: language || 'en'
    });
  }

  async function listAgents(state) {
    const q = state ? '?state=' + encodeURIComponent(state) : '';
    return CLIENT.get('/cgt/govern/gateway/agents' + q);
  }

  async function registerAgent(data) {
    return CLIENT.post('/cgt/govern/gateway/agents', {
      agent_id: data.agent_id, name: data.name || data.agent_id,
      role: data.role, adapter_name: data.adapter_name || 'opencode',
      model: data.model || 'big-pickle',
      system_prompt: data.system_prompt || '',
      language: data.language || 'en'
    });
  }

  async function getAgent(agentId) {
    return CLIENT.get('/cgt/govern/gateway/agents/' + encodeURIComponent(agentId));
  }

  async function agentAction(agentId, action, reason) {
    return CLIENT.post('/cgt/govern/gateway/agents/' + encodeURIComponent(agentId) + '/action', {
      action, reason: reason || ''
    });
  }

  async function agentTrend(agentId) {
    return CLIENT.get('/cgt/govern/gateway/agents/' + encodeURIComponent(agentId) + '/trend');
  }

  async function dashboard() {
    return CLIENT.get('/cgt/govern/gateway/dashboard');
  }

  async function pdfReport() {
    return CLIENT.get('/cgt/govern/gateway/reports/pdf');
  }

  return { evaluate, listAgents, registerAgent, getAgent, agentAction, agentTrend, dashboard, pdfReport };
})();
