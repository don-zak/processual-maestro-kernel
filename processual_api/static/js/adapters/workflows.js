const WORKFLOWS_ADAPTER = (() => {
  async function create(data) {
    return CLIENT.post('/workflows', {
      workflow_id: data.workflow_id,
      goal: data.goal,
      steps: data.steps || []
    });
  }

  async function get(workflowId) {
    return CLIENT.get('/workflows/' + encodeURIComponent(workflowId));
  }

  async function checkpoint(workflowId) {
    return CLIENT.post('/workflows/' + encodeURIComponent(workflowId) + '/checkpoint');
  }

  async function governance(workflowId) {
    return CLIENT.get('/workflows/' + encodeURIComponent(workflowId) + '/governance');
  }

  return { create, get, checkpoint, governance };
})();
