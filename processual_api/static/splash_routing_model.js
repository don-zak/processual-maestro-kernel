import { REFERENCE_BLUEPRINT, corridorFor } from './splash_reference_blueprint.js';

export const STAGE = Object.freeze({ width: 1672, height: 941 });

export const CORE = Object.freeze({
  left: 624,
  right: 1048,
  top: 233,
  bottom: 653,
  centerX: 836,
  centerY: 443,
});

export const ROUTE_WEIGHTS = REFERENCE_BLUEPRINT.routeWeights;
export const COLORS = Object.freeze({
  cyan: '#36bfff',
  teal: '#23d8c8',
  lime: '#a7d67b',
  amber: '#f5a623',
  violet: '#c16fff',
});

export const CONTRACT = Object.freeze({
  version: REFERENCE_BLUEPRINT.version,
  pinCount: 120,
  destinationRatioMax: REFERENCE_BLUEPRINT.destinationRatioMax,
  pulseRatioMax: REFERENCE_BLUEPRINT.pulseRatioMax,
  branchRatioMax: REFERENCE_BLUEPRINT.branchRatioMax,
  sideStem: REFERENCE_BLUEPRINT.breakout.side,
  verticalStem: REFERENCE_BLUEPRINT.breakout.vertical,
  reach: REFERENCE_BLUEPRINT.sideReach,
});

const SIDE_Y = Array.from({ length: 30 }, (_, i) => 254 + i * 13);
const EDGE_X = Array.from({ length: 30 }, (_, i) => 650 + i * 13);

function sideColor(side, i) {
  if (side === 'left') {
    if (i < 8) return 'cyan';
    if (i < 15) return 'teal';
    if (i < 22) return i % 4 === 0 ? 'cyan' : 'lime';
    return 'violet';
  }
  if (i < 15) return 'amber';
  if (i < 22) return i % 5 === 0 ? 'amber' : 'teal';
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
  if (slot < 7) return 'short';
  if (slot < 14) return 'medium';
  return 'long';
}

function weightFor(i) {
  return i % 3 === 0 || i % 7 === 0 ? 'thick' : 'thin';
}

function pulseFor(i) {
  return i % 8 === 0 || i % 17 === 0;
}

function branchFor(i) {
  return i % 6 === 2 || i % 13 === 5;
}

function destinationFor(side, i) {
  const moduleIndexes = REFERENCE_BLUEPRINT.modulePins[side] || [];
  const matchIndex = moduleIndexes.indexOf(i);
  if (matchIndex >= 0 && (side === 'left' || side === 'right')) {
    const corridor = corridorFor(side, i);
    if (corridor) {
      const [minY, maxY] = corridor.targetY;
      const slots = Math.max(1, moduleIndexes.filter(idx => idx >= corridor.range[0] && idx <= corridor.range[1]).length - 1);
      const local = moduleIndexes.filter(idx => idx >= corridor.range[0] && idx <= corridor.range[1]).indexOf(i);
      const targetY = Math.round(minY + ((maxY - minY) * (slots ? local / slots : 0.5)));
      return { type: 'module', target: corridor.module, targetY };
    }
  }
  if (side === 'bottom' && moduleIndexes.includes(i)) {
    return { type: 'module', target: 'execution', targetY: 748 };
  }
  return { type: 'field', target: null, targetY: null };
}

export function buildPins() {
  const pins = [];
  SIDE_Y.forEach((y, i) => {
    for (const side of ['left', 'right']) {
      const destination = destinationFor(side, i);
      const corridor = corridorFor(side, i);
      pins.push({
        id: `${side}-${String(i + 1).padStart(2, '0')}`,
        index: i,
        side,
        x: side === 'left' ? CORE.left : CORE.right,
        y,
        color: sideColor(side, i),
        weight: weightFor(i),
        lengthClass: destination.type === 'module' ? 'destination' : lengthClass(i),
        destination,
        corridor,
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
        index: i,
        side,
        x,
        y: side === 'top' ? CORE.top : CORE.bottom,
        color: edgeColor(side, i),
        weight: weightFor(i + 2),
        lengthClass: destination.type === 'module' ? 'destination' : lengthClass(i + 4),
        destination,
        corridor: null,
        branch: destination.type === 'field' && branchFor(i + 3),
        pulse: pulseFor(i + 5),
        variant: (i * 9 + (side === 'bottom' ? 2 : 0)) % 5,
      });
    }
  });
  return pins;
}

export const PINS = Object.freeze(buildPins());
