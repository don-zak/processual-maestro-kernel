const REPORTS_ADAPTER = (() => {
  async function submitFate(data) {
    return CLIENT.post('/reports/fate', {
      workflow_id: data.workflow_id,
      fate_vector: data.fate_vector,
      existence_rank: data.existence_rank
    });
  }

  return { submitFate };
})();
