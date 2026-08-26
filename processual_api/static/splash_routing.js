import { CORE, STAGE, COLORS, ROUTE_WEIGHTS, CONTRACT, PINS } from './splash_routing_model.js';
import { REFERENCE_BLUEPRINT } from './splash_reference_blueprint.js';

const NS = 'http://www.w3.org/2000/svg';
const board = document.getElementById('pcb-board');
const routesLayer = document.getElementById('pcb-routes');
const branchesLayer = document.getElementById('pcb-branches');
const terminalsLayer = document.getElementById('pcb-terminals');
const pulsesLayer = document.getElementById('pcb-pulses');
const reduceMotion = matchMedia('(prefers-reduced-motion: reduce)');
let pulseRoutes = [];
let raf = null;

function E(name, attrs = {}) {
  const el = document.createElementNS(NS, name);
  for (const [key, value] of Object.entries(attrs)) el.setAttribute(key, String(value));
  return el;
}

function clamp(v, min, max) {
  return Math.max(min, Math.min(max, v));
}

function lerp(a, b, t) {
  return a + (b - a) * t;
}

function pointsToD(points) {
  if (!points.length) return '';
  return points.map((p, i) => `${i ? 'L' : 'M'}${Math.round(p[0])} ${Math.round(p[1])}`).join('');
}

function deterministicRange(pin, band) {
  const span = Math.max(1, band[1] - band[0]);
  const n = (pin.index * 19 + pin.variant * 23 + pin.side.length * 11) % span;
  return band[0] + n;
}

function reachFor(pin) {
  if (pin.side === 'top') return deterministicRange(pin, REFERENCE_BLUEPRINT.topReach[pin.lengthClass] || REFERENCE_BLUEPRINT.topReach.medium);
  if (pin.side === 'bottom') return deterministicRange(pin, REFERENCE_BLUEPRINT.bottomReach[pin.lengthClass] || REFERENCE_BLUEPRINT.bottomReach.medium);
  return deterministicRange(pin, REFERENCE_BLUEPRINT.sideReach[pin.lengthClass] || REFERENCE_BLUEPRINT.sideReach.medium);
}

function corridorY(pin) {
  if (!pin.corridor) return pin.y;
  const [minY, maxY] = pin.corridor.fieldY;
  const [lo, hi] = pin.corridor.range;
  const t = hi === lo ? 0.5 : (pin.index - lo) / (hi - lo);
  const base = lerp(minY, maxY, t);
  const jitter = [0, -7, 5, -12, 10][pin.variant] || 0;
  return clamp(base + jitter, minY, maxY);
}

function sideFieldRoute(pin) {
  const dir = pin.side === 'left' ? -1 : 1;
  const stemX = pin.x + dir * CONTRACT.sideStem;
  const reach = reachFor(pin);
  const endX = stemX + dir * reach;
  const cy = corridorY(pin);
  const x1 = stemX + dir * Math.max(22, Math.round(reach * 0.22));
  const x2 = stemX + dir * Math.max(48, Math.round(reach * 0.48));
  const x3 = stemX + dir * Math.max(70, Math.round(reach * 0.74));
  const y1 = lerp(pin.y, cy, 0.22);
  const y2 = lerp(pin.y, cy, 0.54);
  const y3 = lerp(pin.y, cy, 0.82);
  const points = [[pin.x, pin.y], [stemX, pin.y]];

  if (pin.variant === 0) points.push([x1, pin.y], [x1 + dir * 12, y1], [x2, y1], [x2 + dir * 18, y2], [x3, y2], [x3 + dir * 12, y3], [endX, cy]);
  if (pin.variant === 1) points.push([x1, pin.y], [x1 + dir * 18, y1], [x2, y1], [x2 + dir * 10, y2], [x3, y2], [endX, cy]);
  if (pin.variant === 2) points.push([x1, pin.y], [x1 + dir * 10, y1], [x2, y1], [x2 + dir * 22, y2], [x3, y2], [x3 + dir * 12, y3], [endX, cy]);
  if (pin.variant === 3) points.push([x1, pin.y], [x1 + dir * 16, y1], [x2, y1], [x2 + dir * 14, y2], [endX, cy]);
  if (pin.variant === 4) points.push([x1, pin.y], [x1 + dir * 22, y1], [x2, y1], [x2 + dir * 12, y2], [x3, y2], [endX, cy]);
  return points;
}

function sideDestinationRoute(pin) {
  const dir = pin.side === 'left' ? -1 : 1;
  const stemX = pin.x + dir * CONTRACT.sideStem;
  const targetX = pin.side === 'left' ? 396 : 1276;
  const targetY = pin.destination.targetY;
  const width = Math.abs(targetX - stemX);
  const corridor = corridorY(pin);
  const x1 = stemX + dir * Math.round(width * 0.20);
  const x2 = stemX + dir * Math.round(width * 0.44);
  const x3 = stemX + dir * Math.round(width * 0.70);
  const y1 = lerp(pin.y, corridor, 0.28);
  const y2 = lerp(corridor, targetY, 0.38);
  const y3 = lerp(corridor, targetY, 0.72);
  return [
    [pin.x, pin.y], [stemX, pin.y],
    [x1, pin.y], [x1 + dir * 12, y1],
    [x2, y1], [x2 + dir * 18, y2],
    [x3, y2], [x3 + dir * 14, y3],
    [targetX, targetY],
  ];
}

function buildSideRoute(pin) {
  return pin.destination.type === 'module' ? sideDestinationRoute(pin) : sideFieldRoute(pin);
}

function verticalFieldRoute(pin) {
  const dir = pin.side === 'top' ? -1 : 1;
  const stemY = pin.y + dir * CONTRACT.verticalStem;
  const reach = reachFor(pin);
  const endY = stemY + dir * reach;
  const centerBias = (pin.x - CORE.centerX) / 212;
  const outward = centerBias === 0 ? (pin.variant % 2 ? 1 : -1) : Math.sign(centerBias);
  const baseSpread = 14 + Math.abs(centerBias) * 18;
  const variantSpread = [8, 14, 11, 19, 16][pin.variant];
  const x1 = pin.x + outward * (baseSpread * 0.35);
  const x2 = pin.x + outward * (baseSpread + variantSpread * 0.35);
  const x3 = pin.x + outward * (baseSpread + variantSpread);
  const y1 = stemY + dir * Math.max(16, Math.round(reach * 0.22));
  const y2 = stemY + dir * Math.max(32, Math.round(reach * 0.50));
  const y3 = stemY + dir * Math.max(48, Math.round(reach * 0.78));
  const points = [[pin.x, pin.y], [pin.x, stemY]];

  if (pin.variant === 0) points.push([pin.x, y1], [x1, y1 + dir * 10], [x1, y2], [x2, y2 + dir * 12], [x2, y3], [x3, endY]);
  if (pin.variant === 1) points.push([pin.x, y1], [x1, y1 + dir * 14], [x1, y2], [x2, y2 + dir * 10], [x3, endY]);
  if (pin.variant === 2) points.push([pin.x, y1], [x1, y1 + dir * 8], [x1, y2], [x2, y2 + dir * 16], [x2, y3], [x3, endY]);
  if (pin.variant === 3) points.push([pin.x, y1], [x1, y1 + dir * 12], [x2, y2], [x2, y3], [x3, endY]);
  if (pin.variant === 4) points.push([pin.x, y1], [x1, y1 + dir * 16], [x1, y2], [x2, y2 + dir * 10], [x3, endY]);
  return points;
}

function bottomExecutionRoute(pin) {
  const stemY = pin.y + CONTRACT.verticalStem;
  const offset = (pin.index - 14.5) * 12;
  const targetX = CORE.centerX + offset;
  return [
    [pin.x, pin.y], [pin.x, stemY],
    [pin.x, stemY + 22], [targetX, stemY + 42],
    [targetX, 748],
  ];
}

function buildVerticalRoute(pin) {
  if (pin.side === 'bottom' && pin.destination.type === 'module') return bottomExecutionRoute(pin);
  return verticalFieldRoute(pin);
}

function buildRoute(pin) {
  return pin.side === 'left' || pin.side === 'right' ? buildSideRoute(pin) : buildVerticalRoute(pin);
}

function buildBranch(pin, mainPoints) {
  if (!pin.branch || mainPoints.length < 6) return null;
  const originIndex = Math.min(mainPoints.length - 3, 4 + (pin.variant % 2));
  const origin = mainPoints[originIndex];
  if (pin.side === 'left' || pin.side === 'right') {
    const dir = pin.side === 'left' ? -1 : 1;
    const vertical = ((pin.index % 2) ? 1 : -1) * (14 + pin.variant * 4);
    return [origin, [origin[0] + dir * 18, origin[1]], [origin[0] + dir * 34, origin[1] + vertical], [origin[0] + dir * 54, origin[1] + vertical]];
  }
  const dir = pin.side === 'top' ? -1 : 1;
  const horizontal = ((pin.index % 2) ? 1 : -1) * (14 + pin.variant * 4);
  return [origin, [origin[0], origin[1] + dir * 18], [origin[0] + horizontal, origin[1] + dir * 34], [origin[0] + horizontal, origin[1] + dir * 54]];
}

function terminal(points, color, branch = false) {
  const [x, y] = points[points.length - 1];
  return E('circle', {
    cx: x,
    cy: y,
    r: branch ? 1.7 : 2.15,
    fill: color,
    class: 'pcb-terminal',
    style: `color:${color}`,
  });
}

function renderRoute(pin) {
  const points = buildRoute(pin);
  const color = COLORS[pin.color];
  const route = E('path', {
    id: `route-${pin.id}`,
    d: pointsToD(points),
    class: `pcb-route pcb-route-${pin.weight}`,
    stroke: color,
    style: `color:${color}`,
    'stroke-width': ROUTE_WEIGHTS[pin.weight],
    'data-route-id': pin.id,
    'data-pin-id': pin.id,
    'data-side': pin.side,
    'data-kind': pin.destination.type === 'module' ? 'destination' : pin.lengthClass,
    'data-destination': pin.destination.type,
    'data-weight': pin.weight,
    'data-pulse': pin.pulse ? 'yes' : 'no',
  });
  routesLayer.append(route);

  if (pin.destination.type === 'field') terminalsLayer.append(terminal(points, color));

  const branchPoints = buildBranch(pin, points);
  if (branchPoints) {
    const branch = E('path', {
      id: `branch-${pin.id}`,
      d: pointsToD(branchPoints),
      class: 'pcb-route pcb-route-thin pcb-branch',
      stroke: color,
      style: `color:${color}`,
      'stroke-width': ROUTE_WEIGHTS.thin,
      'data-branch-parent': pin.id,
    });
    branchesLayer.append(branch);
    terminalsLayer.append(terminal(branchPoints, color, true));
  }

  if (pin.pulse) pulseRoutes.push({ pin, route, color });
}

function renderSubstrate() {
  const defs = E('defs');
  defs.innerHTML = `
    <pattern id="pcb-grid" width="18" height="18" patternUnits="userSpaceOnUse"><path d="M18 0H0V18" fill="none" stroke="#2a638d" stroke-opacity=".062" stroke-width=".4"/><circle cx="2" cy="2" r=".65" fill="#4aa5d7" fill-opacity=".11"/></pattern>
    <radialGradient id="pcb-halo"><stop stop-color="#0b6fa9" stop-opacity=".17"/><stop offset=".62" stop-color="#06233e" stop-opacity=".05"/><stop offset="1" stop-color="#020712" stop-opacity="0"/></radialGradient>
  `;
  board.prepend(defs);
  board.insertBefore(E('rect', { width: STAGE.width, height: STAGE.height, fill: 'url(#pcb-grid)', class: 'pcb-substrate' }), routesLayer);
  board.insertBefore(E('ellipse', { cx: CORE.centerX, cy: CORE.centerY, rx: 610, ry: 410, fill: 'url(#pcb-halo)', class: 'pcb-substrate' }), routesLayer);
}

function rebuildFabric() {
  routesLayer.replaceChildren();
  branchesLayer.replaceChildren();
  terminalsLayer.replaceChildren();
  pulsesLayer.replaceChildren();
  pulseRoutes = [];
  PINS.forEach(renderRoute);
  const destinations = PINS.filter(p => p.destination.type === 'module').length;
  board.dataset.routingVersion = CONTRACT.version;
  board.dataset.pinCount = String(PINS.length);
  board.dataset.destinationCount = String(destinations);
  board.dataset.destinationRatio = (destinations / PINS.length).toFixed(3);
  board.dataset.pulseCount = String(PINS.filter(p => p.pulse).length);
}

function pulseCircle(color, radius) {
  return E('circle', { r: radius, fill: color, class: 'pcb-pulse', style: `color:${color}` });
}

function mountPulses() {
  pulsesLayer.replaceChildren();
  for (const item of pulseRoutes) {
    item.pulse = pulseCircle(item.color, item.pin.weight === 'thick' ? 2.25 : 1.7);
    item.phase = (item.pin.index * 0.137 + (item.pin.side === 'right' ? 0.23 : item.pin.side === 'bottom' ? 0.41 : 0)) % 1;
    item.speed = 0.000032 + (item.pin.variant * 0.0000035);
    pulsesLayer.append(item.pulse);
  }
}

function animate(now) {
  for (const item of pulseRoutes) {
    const length = item.route.getTotalLength();
    if (!length || !item.pulse) continue;
    const t = (item.phase + now * item.speed) % 1;
    const point = item.route.getPointAtLength(length * t);
    item.pulse.setAttribute('cx', point.x);
    item.pulse.setAttribute('cy', point.y);
  }
  raf = requestAnimationFrame(animate);
}

function restartMotion() {
  if (raf) cancelAnimationFrame(raf);
  mountPulses();
  if (!reduceMotion.matches) raf = requestAnimationFrame(animate);
}

renderSubstrate();
rebuildFabric();
restartMotion();
reduceMotion.addEventListener?.('change', restartMotion);
