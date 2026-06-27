const ADAPTERS_ADAPTER = (() => {
  async function status() {
    return CLIENT.get('/adapters/status');
  }

  async function configure(provider, apiKey, model, baseUrl) {
    return CLIENT.post('/adapters/configure', {
      provider, api_key: apiKey, model, base_url: baseUrl
    });
  }

  async function test(provider) {
    return CLIENT.post('/adapters/test', { provider });
  }

  return { status, configure, test };
})();
