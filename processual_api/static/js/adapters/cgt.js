const CGT_ADAPTER = (() => {
  async function evaluate(data) {
    return CLIENT.post('/cgt/evaluate', {
      transition_channel: data.transition_channel,
      compatibility: data.compatibility, retention: data.retention,
      harmony: data.harmony, fatigue: data.fatigue,
      complexity: data.complexity, shock: data.shock,
      dwell_time: data.dwell_time, carrier: data.carrier,
      diversity: data.diversity, novelty: data.novelty,
      lift: data.lift
    });
  }

  return { evaluate };
})();
