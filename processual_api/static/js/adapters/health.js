const HEALTH_ADAPTER = (() => {
  async function live() {
    return CLIENT.get('/health/live');
  }

  async function ready() {
    return CLIENT.get('/health/ready');
  }

  return { live, ready };
})();
