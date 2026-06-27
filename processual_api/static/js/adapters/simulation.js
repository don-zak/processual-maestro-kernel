const SIMULATION_ADAPTER = (() => {
  async function run() {
    return CLIENT.post('/cgt/govern/simulate');
  }

  async function listReports() {
    return CLIENT.get('/cgt/govern/simulate/reports');
  }

  async function reportPdf(simId) {
    return CLIENT.get('/cgt/govern/simulate/reports/' + encodeURIComponent(simId) + '/pdf');
  }

  return { run, listReports, reportPdf };
})();
