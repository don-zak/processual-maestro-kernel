import { CORE, STAGE, COLORS, ROUTE_WEIGHTS, CONTRACT, PINS } from './splash_routing_model.js';

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

function reachFor(pin) {
  const band = CONTRACT.reach[pin.lengthClass] || CONTRACT.reach.medium;
  const span = band[1] - band[0];
  return band[0] + ((pin.variant * 17 + Number(pin.id.slice(-2)) * 11) % Math.max(1, span));
}

function sideSign(side) {
  return side === 'left' || side === 'top' ? -1 : 1;
}

function spreadOffset(pin, stage) {
  const i = Number(pin.id.slice(-2));
  const base = ((i % 7) - 3) * (stage === 1 ? 2.2 : stage === 2 ? 4.4 : 6.4);
  const variant = [0, 6, -5, 10, -9][pin.variant] || 0;
  return base + variant * (stage / 3);
}

function pointsToD(points) {
  if (!points.length) return '';
  return points.map((p, i) => `${i ? 'L' : 'M'}${Math.round(p[0])} ${Math.round(p[1])}`).join('');
}

function buildSideRoute(pin) {
  const dir = pin.side === 'left' ? -1 : 1;
  const stemX = pin.x + dir * CONTRACT.sideStem;
  const points = [[pin.x, pin.y], [stemX, pin.y]];

  if (pin.destination.type === 'module') {
    const targetX = pin.side === 'left' ? 396 : 1276;
    const targetY = pin.destination.targetY;
    const width = Math.abs(targetX - stemX);
    const x1 = stemX + dir * Math.round(width * 0.24);
    const x2 = stemX + dir * Math.round(width * 0.52);
    const x3 = stemX + dir * Math.round(width * 0.78);
    const y1 = pin.y + (targetY - pin.y) * 0.18;
    const y2 = pin.y + (targetY - pin.y) * 0.48;
    const y3 = pin.y + (targetY - pin.y) * 0.76;
    points.push([x1, pin.y], [x1 + dir * 16, y1], [x2, y1], [x2 + dir * 18, y2], [x3, y2], [x3 + dir * 14, y3], [targetX, targetY]);
    return points;
  }

  const reach = reachFor(pin);
  const endX = stemX + dir * reach;
  const x1 = stemX + dir * Math.round(reach * 0.26);
  const x2 = stemX + dir * Math.round(reach * 0.56);
  const x3 = stemX + dir * Math.round(reach * 0.82);
  const o1 = spreadOffset(pin, 1);
  const o2 = spreadOffset(pin, 2);
  const o3 = spreadOffset(pin, 3);

  points.push([x1, pin.y]);
  if (pin.variant === 0) points.push([x1 + dir * 14, pin.y + o1], [x2, pin.y + o1], [x2 + dir * 18, pin.y + o2], [x3, pin.y + o2], [endX, pin.y + o3]);
  if (pin.variant === 1) points.push([x1 + dir * 22, pin.y + o1], [x2, pin.y + o1], [x2 + dir * 12, pin.y + o2], [endX, pin.y + o3]);
  if (pin.variant === 2) points.push([x1 + dir * 12, pin.y + o1], [x2, pin.y + o1], [x2 + dir * 24, pin.y + o2], [x3, pin.y + o2], [x3 + dir * 12, pin.y + o3], [endX, pin.y + o3]);
  if (pin.variant === 3) points.push([x1 + dir * 18, pin.y + o1], [x2, pin.y + o1], [x2 + dir * 18, pin.y + o2], [endX, pin.y + o2]);
  if (pin.variant === 4) points.push([x1 + dir * 26, pin.y + o1], [x2, pin.y + o1], [x2 + dir * 12, pin.y + o2], [x3, pin.y + o2], [endX, pin.y + o3]);
  return points;
}

function buildVerticalRoute(pin) {
  const dir = pin.side === 'top' ? -1 : 1;
  const stemY = pin.y + dir * CONTRACT.verticalStem;
  const points = [[pin.x, pin.y], [pin.x, stemY]];

  if (pin.destination.type === 'module' && pin.destination.target === 'execution') {
    const targetX = 836 + (Number(pin.id.slice(-2)) - 14) * 14;
    const targetY = pin.destination.targetY;
    points.push([pin.x, stemY + dir * 30], [targetX, stemY + dir * 56], [targetX, targetY]);
    return points;
  }

  const reach = reachFor(pin);
  const endY = stemY + dir * reach;
  const y1 = stemY + dir * Math.round(reach * 0.27);
  const y2 = stemY + dir * Math.round(reach * 0.58);
  const y3 = stemY + dir * Math.round(reach * 0.84);
  const o1 = spreadOffset(pin, 1) * 0.7;
  const o2 = spreadOffset(pin, 2) * 0.8;
  const o3 = spreadOffset(pin, 3) * 0.9;

  points.push([pin.x, y1]);
  if (pin.variant === 0) points.push([pin.x + o1, y1 + dir * 12], [pin.x + o1, y2], [pin.x + o2, y2 + dir * 14], [pin.x + o2, y3], [pin.x + o3, endY]);
  if (pin.variant === 1) points.push([pin.x + o1, y1 + dir * 18], [pin.x + o1, y2], [pin.x + o2, y2 + dir * 12], [pin.x + o3, endY]);
  if (pin.variant === 2) points.push([pin.x + o1, y1 + dir * 10], [pin.x + o1, y2], [pin.x + o2, y2 + dir * 20], [pin.x + o2, y3], [pin.x + o3, endY]);
  if (pin.variant === 3) points.push([pin.x + o1, y1 + dir * 14], [pin.x + o2, y2], [pin.x + o2, y3], [pin.x + o3, endY]);
  if (pin.variant === 4) points.push([pin.x + o1, y1 + dir * 20], [pin.x + o1, y2], [pin.x + o2, y2 + dir * 12], [pin.x + o3, endY]);
  return points;
}

function buildRoute(pin) {
  return pin.side === 'left' || pin.side === 'right' ? buildSideRoute(pin) : buildVerticalRoute(pin);
}

function buildBranch(pin, mainPoints) {
  if (!pin.branch || mainPoints.length < 5) return null;
  const originIndex = Math.min(mainPoints.length - 2, 3 + (pin.variant % 2));
  const origin = mainPoints[originIndex];
  const sign = sideSign(pin.side);
  if (pin.side === 'left' || pin.side === 'right') {
    const dir = pin.side === 'left' ? -1 : 1;
    const vertical = ((Number(pin.id.slice(-2)) % 2) ? 1 : -1) * (18 + pin.variant * 4);
    return [origin, [origin[0] + dir * 24, origin[1]], [origin[0] + dir * 42, origin[1] + vertical], [origin[0] + dir * 74, origin[1] + vertical]];
  }
  const horizontal = ((Number(pin.id.slice(-2)) % 2) ? 1 : -1) * (18 + pin.variant * 4);
  const dir = pin.side === 'top' ? -1 : 1;
  return [origin, [origin[0], origin[1] + dir * 24], [origin[0] + horizontal, origin[1] + dir * 42], [origin[0] + horizontal, origin[1] + dir * 72]];
}

function terminal(points, color, branch = false) {
  const [x, y] = points[points.length - 1];
  return E('circle', {
    cx: x,
    cy: y,
    r: branch ? 1.8 : 2.2,
    fill: color,
    class: 'pcb-terminal',
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
    <pattern id="pcb-grid" width="18" height="18" patternUnits="userSpaceOnUse"><path d="M18 0H0V18" fill="none" stroke="#2a638d" stroke-opacity=".065" stroke-width=".4"/><circle cx="2" cy="2" r=".65" fill="#4aa5d7" fill-opacity=".10"/></pattern>
    <radialGradient id="pcb-halo"><stop stop-color="#0b6fa9" stop-opacity=".16"/><stop offset=".62" stop-color="#06233e" stop-opacity=".05"/><stop offset="1" stop-color="#020712" stop-opacity="0"/></radialGradient>
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
  board.dataset.routingVersion = CONTRACT.version;
  board.dataset.pinCount = String(PINS.length);
  board.dataset.destinationCount = String(PINS.filter(p => p.destination.type === 'module').length);
  board.dataset.pulseCount = String(PINS.filter(p => p.pulse).length);
}

function pulseCircle(color, radius) {
  return E('circle', { r: radius, fill: color, class: 'pcb-pulse', style: `color:${color}` });
}

function mountPulses() {
  pulsesLayer.replaceChildren();
  for (const item of pulseRoutes) {
    item.pulse = pulseCircle(item.color, item.pin.weight === 'thick' ? 2.4 : 1.8);
    item.phase = (Number(item.pin.id.slice(-2)) * 0.137 + (item.pin.side === 'right' ? 0.23 : 0)) % 1;
    item.speed = 0.000035 + (item.pin.variant * 0.000004);
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
