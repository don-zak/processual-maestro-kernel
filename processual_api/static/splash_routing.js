import { STAGE, COLORS } from './splash_routing_model.js';
import { REFERENCE_ROUTE_TRACE } from './splash_reference_routes.js';

const NS = 'http://www.w3.org/2000/svg';
const board = document.getElementById('pcb-board');
const routesLayer = document.getElementById('pcb-routes');
const branchesLayer = document.getElementById('pcb-branches');
const terminalsLayer = document.getElementById('pcb-terminals');
const pulsesLayer = document.getElementById('pcb-pulses');
const reduceMotion = matchMedia('(prefers-reduced-motion: reduce)');
let pulseRoutes = [];
let raf = null;

const REF = REFERENCE_ROUTE_TRACE.meta;
const [REF_LEFT, REF_TOP, REF_RIGHT, REF_BOTTOM] = REF.core_reference_px;
const TARGET = Object.freeze({ left: 624, top: 233, right: 1048, bottom: 653 });
const ROUTE_WEIGHTS = Object.freeze({ thick: 1.08, thin: 0.66 });

function E(name, attrs = {}) {
  const el = document.createElementNS(NS, name);
  for (const [key, value] of Object.entries(attrs)) el.setAttribute(key, String(value));
  return el;
}

function mapAxis(v, a0, a1, b0, b1, sourceMax, targetMax) {
  if (v <= a0) return (v / a0) * b0;
  if (v <= a1) return b0 + ((v - a0) / (a1 - a0)) * (b1 - b0);
  return b1 + ((v - a1) / (sourceMax - a1)) * (targetMax - b1);
}

function mapPoint([x, y]) {
  return [
    mapAxis(x, REF_LEFT, REF_RIGHT, TARGET.left, TARGET.right, REF.source_width, STAGE.width),
    mapAxis(y, REF_TOP, REF_BOTTOM, TARGET.top, TARGET.bottom, REF.source_height, STAGE.height),
  ];
}

function pointsToD(points) {
  return points.map((p, i) => `${i ? 'L' : 'M'}${p[0].toFixed(2)} ${p[1].toFixed(2)}`).join('');
}

function terminal(points, color, radius = 1.9) {
  const [x, y] = points[points.length - 1];
  return E('circle', { cx: x, cy: y, r: radius, fill: color, class: 'pcb-terminal', style: `color:${color}` });
}

function selectedForPulse(index, weight) {
  if (weight === 'thick') return index % 7 === 0;
  return index % 13 === 3;
}

function selectedForTerminal(index, segment) {
  if (segment.length < 72) return true;
  return index % 4 === 1;
}

function renderReferenceTrace() {
  routesLayer.replaceChildren();
  branchesLayer.replaceChildren();
  terminalsLayer.replaceChildren();
  pulsesLayer.replaceChildren();
  pulseRoutes = [];

  REFERENCE_ROUTE_TRACE.segments.forEach((segment, index) => {
    const points = segment.points.map(mapPoint);
    const color = COLORS[segment.color] || COLORS.cyan;
    const weight = segment.weight === 'thick' || index % 5 === 0 ? 'thick' : 'thin';
    const route = E('path', {
      id: `reference-${segment.id}`,
      d: pointsToD(points),
      class: `pcb-route pcb-route-${weight}`,
      stroke: color,
      'stroke-width': ROUTE_WEIGHTS[weight],
      style: `color:${color}`,
      'data-route-id': segment.id,
      'data-source': 'pivot-reference-image',
      'data-weight': weight,
      'data-reference-length': segment.length,
    });
    routesLayer.append(route);

    if (selectedForTerminal(index, segment)) terminalsLayer.append(terminal(points, color, weight === 'thick' ? 2.15 : 1.75));
    if (selectedForPulse(index, weight)) pulseRoutes.push({ route, color, weight, index });
  });

  board.dataset.routingVersion = 'A3-splash-reference-pixeltrace-v22';
  board.dataset.referenceSource = 'pivot-reference-image';
  board.dataset.referenceSegments = String(REFERENCE_ROUTE_TRACE.segments.length);
}

function renderSubstrate() {
  const oldDefs = board.querySelector('defs[data-reference-trace]');
  if (oldDefs) oldDefs.remove();
  const defs = E('defs', { 'data-reference-trace': 'true' });
  defs.innerHTML = `
    <pattern id="pcb-grid" width="18" height="18" patternUnits="userSpaceOnUse"><path d="M18 0H0V18" fill="none" stroke="#2a638d" stroke-opacity=".06" stroke-width=".4"/><circle cx="2" cy="2" r=".65" fill="#4aa5d7" fill-opacity=".10"/></pattern>
    <radialGradient id="pcb-halo"><stop stop-color="#0b6fa9" stop-opacity=".15"/><stop offset=".62" stop-color="#06233e" stop-opacity=".045"/><stop offset="1" stop-color="#020712" stop-opacity="0"/></radialGradient>`;
  board.prepend(defs);
  if (!board.querySelector('.pcb-substrate')) {
    board.insertBefore(E('rect', { width: STAGE.width, height: STAGE.height, fill: 'url(#pcb-grid)', class: 'pcb-substrate' }), routesLayer);
    board.insertBefore(E('ellipse', { cx: 836, cy: 443, rx: 610, ry: 410, fill: 'url(#pcb-halo)', class: 'pcb-substrate' }), routesLayer);
  }
}

function mountPulses() {
  pulsesLayer.replaceChildren();
  for (const item of pulseRoutes) {
    item.pulse = E('circle', {
      r: item.weight === 'thick' ? 2.25 : 1.65,
      fill: item.color,
      class: 'pcb-pulse',
      style: `color:${item.color}`,
    });
    item.phase = (item.index * 0.173) % 1;
    item.speed = item.weight === 'thick' ? 0.000030 : 0.000024;
    pulsesLayer.append(item.pulse);
  }
}

function animate(now) {
  for (const item of pulseRoutes) {
    const length = item.route.getTotalLength();
    if (!length || !item.pulse) continue;
    const point = item.route.getPointAtLength(length * ((item.phase + now * item.speed) % 1));
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
renderReferenceTrace();
restartMotion();
reduceMotion.addEventListener?.('change', restartMotion);
