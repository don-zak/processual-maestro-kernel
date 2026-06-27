const TELEMETRY_ADAPTER = (() => {
  async function ingest(points) {
    return CLIENT.post('/telemetry/ingest', { points });
  }

  return { ingest };
})();
