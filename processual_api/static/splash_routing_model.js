export const STAGE = Object.freeze({ width: 1672, height: 941 });

export const CORE = Object.freeze({
  left: 624,
  right: 1048,
  top: 233,
  bottom: 653,
  centerX: 836,
  centerY: 443,
});

export const ROUTE_WEIGHTS = Object.freeze({ thick: 1.1, thin: 0.68 });
export const COLORS = Object.freeze({
  cyan: '#36bfff',
  teal: '#23d8c8',
  lime: '#a7d67b',
  amber: '#f5a623',
  violet: '#c16fff',
});

export const CONTRACT = Object.freeze({
  version: 'A3-splash-routing-v20',
  destinationRatioMax: 0.20,
  pulseRatioMax: 0.20,
  branchRatioMax: 0.26,
  sideStem: 46,
  verticalStem: 38,
  reach: {
    short: [82, 126],
    medium: [146, 218],
    long: [236, 322],
  },
});

const SIDE_Y = Array.from({ length: 28 }, (_, i) => 270 + i * 12);
const EDGE_X = Array.from({ length: 30 }, (_, i) => 650 + i * 13);

function sideColor(side, i) {
  if (side === 'left') {
    if (i < 7) return 'cyan';
    if (i < 14) return 'teal';
    if (i < 21) return i % 4 === 0 ? 'cyan' : 'lime';
    return 'violet';
  }
  if (i < 14) return 'amber';
  if (i < 21) return i % 5 === 0 ? 'amber' : 'teal';
  return 'violet';
}

function edgeColor(side, i) {
  if (side === 'top') {
    if (i < 10) return 'cyan';
    if (i < 14) return 'teal';
    return 'amber';
  }
  if (i < 8) return 'cyan';
  if (i < 12) return 'teal';
  if (i < 20) return 'amber';
  return 'violet';
}

function lengthClass(i) {
  const slot = i % 20;
  if (slot < 6) return 'short';
  if (slot < 13) return 'medium';
  return 'long';
}

function weightFor(i) {
  return i % 3 === 0 || i % 7 === 0 ? 'thick' : 'thin';
}

function pulseFor(i) {
  return i % 7 === 0 || i % 13 === 0;
}

function branchFor(i) {
  return i % 5 === 2 || i % 11 === 4;
}

const SIDE_DESTINATIONS = Object.freeze({
  left: [
    { indexes: [1, 5], target: 'governance', y: 162 },
    { indexes: [8, 12], target: 'supervision', y: 339 },
    { indexes: [15, 19], target: 'calibration', y: 518 },
    { indexes: [22, 26], target: 'orchestration', y: 697 },
  ],
  right: [
    { indexes: [1, 5], target: 'routing', y: 162 },
    { indexes: [8, 12], target: 'policy', y: 339 },
    { indexes: [15, 19], target: 'feedback', y: 518 },
    { indexes: [22, 26], target: 'control', y: 697 },
  ],
});

function destinationFor(side, i) {
  const groups = SIDE_DESTINATIONS[side] || [];
  for (const group of groups) {
    const pos = group.indexes.indexOf(i);
    if (pos >= 0) return { type: 'module', target: group.target, targetY: group.y + pos * 8 - 4 };
  }
  if (side === 'bottom' && [13, 14, 15].includes(i)) {
    return { type: 'module', target: 'execution', targetY: 748 };
  }
  return { type: 'field', target: null, targetY: null };
}

export function buildPins() {
  const pins = [];
  SIDE_Y.forEach((y, i) => {
    for (const side of ['left', 'right']) {
      const destination = destinationFor(side, i);
      pins.push({
        id: `${side}-${String(i + 1).padStart(2, '0')}`,
        side,
        x: side === 'left' ? CORE.left : CORE.right,
        y,
        color: sideColor(side, i),
        weight: weightFor(i),
        lengthClass: destination.type === 'module' ? 'destination' : lengthClass(i),
        destination,
        branch: destination.type === 'field' && branchFor(i),
        pulse: pulseFor(i),
        variant: (i * 7 + (side === 'right' ? 3 : 0)) % 5,
      });
    }
  });
  EDGE_X.forEach((x, i) => {
    for (const side of ['top', 'bottom']) {
      const destination = destinationFor(side, i);
      pins.push({
        id: `${side}-${String(i + 1).padStart(2, '0')}`,
        side,
        x,
        y: side === 'top' ? CORE.top : CORE.bottom,
        color: edgeColor(side, i),
        weight: weightFor(i + 2),
        lengthClass: destination.type === 'module' ? 'destination' : lengthClass(i + 4),
        destination,
        branch: destination.type === 'field' && branchFor(i + 3),
        pulse: pulseFor(i + 5),
        variant: (i * 9 + (side === 'bottom' ? 2 : 0)) % 5,
      });
    }
  });
  return pins;
}

export const PINS = Object.freeze(buildPins());
