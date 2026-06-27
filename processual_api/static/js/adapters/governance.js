const GOVERNANCE_ADAPTER = (() => {
  async function status() {
    return CLIENT.get('/governance/status');
  }

  return { status };
})();
