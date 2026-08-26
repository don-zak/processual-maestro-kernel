export const REFERENCE_BLUEPRINT = Object.freeze({
  version: 'A3-splash-reference-blueprint-v21',
  source: 'pivot-reference-image',
  routeWeights: Object.freeze({ thick: 1.08, thin: 0.66 }),
  destinationRatioMax: 0.16,
  pulseRatioMax: 0.18,
  branchRatioMax: 0.24,
  breakout: Object.freeze({ side: 44, vertical: 34 }),
  sideReach: Object.freeze({ short: [58, 86], medium: [98, 136], long: [146, 188] }),
  topReach: Object.freeze({ short: [42, 66], medium: [76, 108], long: [118, 164] }),
  bottomReach: Object.freeze({ short: [38, 58], medium: [64, 92], long: [98, 132] }),
  sideCorridors: Object.freeze({
    left: Object.freeze([
      Object.freeze({ range: [0, 7], module: 'governance', targetY: [128, 205], fieldY: [105, 232] }),
      Object.freeze({ range: [8, 14], module: 'supervision', targetY: [306, 372], fieldY: [278, 402] }),
      Object.freeze({ range: [15, 21], module: 'calibration', targetY: [486, 548], fieldY: [448, 575] }),
      Object.freeze({ range: [22, 29], module: 'orchestration', targetY: [652, 718], fieldY: [612, 760] }),
    ]),
    right: Object.freeze([
      Object.freeze({ range: [0, 7], module: 'routing', targetY: [128, 205], fieldY: [105, 232] }),
      Object.freeze({ range: [8, 14], module: 'policy', targetY: [306, 372], fieldY: [278, 402] }),
      Object.freeze({ range: [15, 21], module: 'feedback', targetY: [486, 548], fieldY: [448, 575] }),
      Object.freeze({ range: [22, 29], module: 'control', targetY: [652, 718], fieldY: [612, 760] }),
    ]),
  }),
  modulePins: Object.freeze({
    left: Object.freeze([2, 6, 10, 13, 17, 20, 24, 28]),
    right: Object.freeze([1, 5, 9, 12, 16, 20, 24, 27]),
    bottom: Object.freeze([14, 15]),
  }),
  referencePrinciples: Object.freeze([
    'all-visible-teeth-launch',
    'aligned-breakout-before-divergence',
    'corridor-guided-progressive-spread',
    'destination-routes-are-minority',
    'staggered-short-medium-long-field-terminations',
    'two-route-weights-only',
    'selective-pulses-on-both-weights',
    'branches-after-breakout-only',
  ]),
});

export function corridorFor(side, index) {
  const corridors = REFERENCE_BLUEPRINT.sideCorridors[side] || [];
  return corridors.find(c => index >= c.range[0] && index <= c.range[1]) || null;
}
