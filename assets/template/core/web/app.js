const canvas = document.getElementById("circuitCanvas");
const context = canvas.getContext("2d");
const connectionOverlay = document.getElementById("connectionOverlay");
const overlayContext = connectionOverlay.getContext("2d");
const serialLog = document.getElementById("serialLog");
const partsLayer = document.getElementById("partsLayer");

const app = {
  config: null,
  boardGeometries: new Map(),
  diagram: null,
  state: null,
  cursor: 0,
  parts: [],
  hitAreas: [],
  scale: 1,
  offsetX: 0,
  offsetY: 0,
  pointerPart: null,
  clearedBefore: 0,
  partElements: new Map(),
  canvasWidth: 0,
  canvasHeight: 0,
  canvasRatio: 0,
  inputQueue: Promise.resolve(),
  wirePaths: [],
  hoveredWire: null,
  wireRoutes: {},
  groundBusY: null,
  interactionMode: "run",
  drag: null,
  wireDrag: null,
  selectedPartId: null,
  selectedWireId: null,
  layoutQueue: Promise.resolve(),
  unloading: false,
  defaultRouteScheduled: false,
};

const colors = {
  green: "#65d887",
  black: "#8b958e",
  orange: "#f39a48",
  red: "#ff6d65",
  blue: "#4ac7ff",
  purple: "#bd86ff",
  cyan: "#54d9d1",
  yellow: "#f0c65a",
  pink: "#ff7ad9",
};

const keyboardBindings = new Map();
const heldKeyboardCodes = new Set();

function getPath(value, path, fallback = null) {
  if (!path) return value;
  const result = String(path).split(".").reduce((current, key) => {
    if (current === null || current === undefined) return undefined;
    return current[/^\d+$/.test(key) ? Number(key) : key];
  }, value);
  return result === undefined ? fallback : result;
}

function interpolate(template, state = app.state) {
  return String(template || "").replace(/\{([^}]+)\}/g, (_, path) => getPath(state, path, ""));
}

function controlFor(part) {
  return app.config?.controls?.[part?.id] || null;
}

function matchesRule(rule) {
  const value = getPath(app.state, rule.path);
  if (Object.hasOwn(rule, "equals") && value !== rule.equals) return false;
  if (rule.truthy && !value) return false;
  if (rule.unlessPath) {
    const blocked = getPath(app.state, rule.unlessPath);
    if (Object.hasOwn(rule, "unlessEquals") ? blocked === rule.unlessEquals : Boolean(blocked)) return false;
  }
  return true;
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}

function sendInput(payload) {
  const request = app.inputQueue.then(async () => {
    app.state = await api("/api/input", { method: "POST", body: JSON.stringify(payload) });
    updateStatus();
    draw();
  });
  app.inputQueue = request.catch((error) => console.error(error));
  return request;
}

function resizeCanvas(force = false) {
  const ratio = window.devicePixelRatio || 1;
  const bounds = canvas.getBoundingClientRect();
  const width = Math.max(1, Math.round(bounds.width));
  const height = Math.max(1, Math.round(bounds.height));
  if (!force &&
    width === app.canvasWidth
    && height === app.canvasHeight
    && ratio === app.canvasRatio
  ) return;
  app.canvasWidth = width;
  app.canvasHeight = height;
  app.canvasRatio = ratio;
  canvas.width = Math.max(1, Math.round(bounds.width * ratio));
  canvas.height = Math.max(1, Math.round(bounds.height * ratio));
  connectionOverlay.width = canvas.width;
  connectionOverlay.height = canvas.height;
  context.setTransform(ratio, 0, 0, ratio, 0, 0);
  overlayContext.setTransform(ratio, 0, 0, ratio, 0, 0);
  fitCircuit();
}

function fitCircuit() {
  if (!app.diagram) return;
  const bounds = canvas.getBoundingClientRect();
  const world = diagramBounds();
  const padding = Math.min(78, Math.max(26, bounds.width * 0.08));
  app.scale = Math.min(
    (bounds.width - padding * 2) / world.width,
    (bounds.height - padding * 2) / world.height,
    1.45,
  );
  app.offsetX = (bounds.width - world.width * app.scale) / 2 - world.left * app.scale;
  app.offsetY = (bounds.height - world.height * app.scale) / 2 - world.top * app.scale;
  draw();
}

function diagramBounds() {
  const parts = app.diagram.parts;
  const bounds = parts.map(partBounds);
  const routePoints = Object.values(app.wireRoutes || {});
  const routeXs = routePoints.map((point) => point.x);
  const routeYs = routePoints.map((point) => point.y);
  if (app.groundBusY !== null) routeYs.push(app.groundBusY);
  const left = Math.min(...bounds.map((item) => item.left), ...routeXs) - 25;
  const top = Math.min(...bounds.map((item) => item.top), ...routeYs) - 45;
  const right = Math.max(...bounds.map((item) => item.right), ...routeXs) + 30;
  const bottom = Math.max(...bounds.map((item) => item.bottom), ...routeYs) + 35;
  return { left, top, width: right - left, height: bottom - top };
}

function partBounds(part) {
  const size = partSize(part);
  const radians = (part.rotate || 0) * Math.PI / 180;
  const width = Math.abs(size.width * Math.cos(radians)) + Math.abs(size.height * Math.sin(radians));
  const height = Math.abs(size.width * Math.sin(radians)) + Math.abs(size.height * Math.cos(radians));
  const centerX = (part.left || 0) + size.width / 2;
  const centerY = (part.top || 0) + size.height / 2;
  return {
    left: centerX - width / 2,
    top: centerY - height / 2,
    right: centerX + width / 2,
    bottom: centerY + height / 2,
  };
}

function partSize(part) {
  return app.config?.partSizes?.[part.type] || { width: 80, height: 34 };
}

function worldPoint(part, localX, localY) {
  return {
    x: app.offsetX + ((part.left || 0) + localX) * app.scale,
    y: app.offsetY + ((part.top || 0) + localY) * app.scale,
  };
}

function worldPosition(x, y) {
  return {
    x: app.offsetX + x * app.scale,
    y: app.offsetY + y * app.scale,
  };
}

function canvasPosition(x, y) {
  return {
    x: (x - app.offsetX) / app.scale,
    y: (y - app.offsetY) / app.scale,
  };
}

function connectionId(connection) {
  return `${connection[0]}>${connection[1]}`;
}

function longestSegmentMidpoint(points) {
  let longest = { length: -1, point: points[0] };
  for (let index = 1; index < points.length; index += 1) {
    const start = points[index - 1];
    const end = points[index];
    const length = Math.hypot(end.x - start.x, end.y - start.y);
    if (length > longest.length) {
      longest = {
        length,
        point: { x: (start.x + end.x) / 2, y: (start.y + end.y) / 2 },
      };
    }
  }
  return longest.point;
}

function routedPoints(start, end, route) {
  if (route.style === "hv") {
    return [start, { x: route.x, y: start.y }, { x: route.x, y: end.y }, end];
  }
  if (route.style === "vh") {
    return [start, { x: start.x, y: route.y }, { x: end.x, y: route.y }, end];
  }
  return [
    start,
    { x: route.x, y: start.y },
    route,
    { x: end.x, y: route.y },
    end,
  ];
}

function routeControlPoint(start, end, route) {
  if (route.style === "hv") return { x: route.x, y: (start.y + end.y) / 2 };
  if (route.style === "vh") return { x: (start.x + end.x) / 2, y: route.y };
  return route;
}

function routeSegments(points) {
  return points.slice(1)
    .map((end, index) => ({ start: points[index], end }))
    .filter(segment => Math.hypot(
      segment.end.x - segment.start.x,
      segment.end.y - segment.start.y,
    ) >= 0.5);
}

function clientPointToCanvas(x, y) {
  const bounds = canvas.getBoundingClientRect();
  return { x: x - bounds.left, y: y - bounds.top };
}

function pinPoint(reference) {
  const [id, pin] = reference.split(":");
  const part = app.diagram.parts.find((candidate) => candidate.id === id);
  if (!part) return null;
  const visual = app.partElements.get(part.id);
  const boardGeometry = app.boardGeometries.get(part.type);
  if (boardGeometry) {
    const position = boardGeometry.pins[pin];
    if (!visual || !position) return null;
    const bounds = visual.element.getBoundingClientRect();
    return clientPointToCanvas(
      bounds.left + position[0] / boardGeometry.width * bounds.width,
      bounds.top + position[1] / boardGeometry.height * bounds.height,
    );
  }
  const geometry = visual?.pinGeometry;
  const pinInfo = geometry?.pins.get(pin);
  const matrix = geometry?.svg.getScreenCTM();
  if (!pinInfo || !matrix || geometry.width <= 0 || geometry.height <= 0) return null;
  const viewBox = geometry.svg.viewBox.baseVal;
  const svgPoint = new DOMPoint(
    viewBox.x + pinInfo.x / geometry.width * viewBox.width,
    viewBox.y + pinInfo.y / geometry.height * viewBox.height,
  ).matrixTransform(matrix);
  return clientPointToCanvas(svgPoint.x, svgPoint.y);
}

function draw() {
  if (!app.diagram) return;
  layoutPartElements();
  const bounds = canvas.getBoundingClientRect();
  context.clearRect(0, 0, bounds.width, bounds.height);
  overlayContext.clearRect(0, 0, bounds.width, bounds.height);
  drawGrid(bounds.width, bounds.height);
  drawConnections();
  drawTextParts();
  updateHitAreas();
  updateWiringPanel();
}

function drawGrid(width, height) {
  context.fillStyle = "#141715";
  context.fillRect(0, 0, width, height);
  context.fillStyle = "#242824";
  for (let y = 14; y < height; y += 22) {
    for (let x = 14; x < width; x += 22) context.fillRect(x, y, 1, 1);
  }
}

function drawConnections() {
  app.wirePaths = [];
  const grounds = app.diagram.connections.filter(isGroundConnection);
  if (app.selectedWireId !== "ground-bus") drawGroundNetwork(grounds);
  const signals = app.diagram.connections.filter(connection => !isGroundConnection(connection));
  signals.sort((left, right) => Number(connectionId(left) === app.selectedWireId)
    - Number(connectionId(right) === app.selectedWireId));
  signals.forEach((connection, index) => {
    const start = pinPoint(connection[0]);
    const end = pinPoint(connection[1]);
    if (!start || !end) return;
    const id = connectionId(connection);
    const savedRoute = app.wireRoutes[id];
    const route = savedRoute
      ? { ...worldPosition(savedRoute.x, savedRoute.y), style: savedRoute.style }
      : { x: start.x + (end.x - start.x) * 0.52, y: end.y };
    const path = new Path2D();
    const points = routedPoints(start, end, route);
    path.moveTo(points[0].x, points[0].y);
    for (const point of points.slice(1)) path.lineTo(point.x, point.y);
    const color = colors[connection[2]] || connection[2] || "#66706a";
    const selected = app.selectedWireId === id;
    const hovered = app.hoveredWire === id || selected;
    const muted = Boolean(app.selectedWireId && !selected);
    context.lineWidth = Math.max(hovered ? 4 : 2, (hovered ? 4 : 2.4) * app.scale);
    context.strokeStyle = color;
    context.globalAlpha = muted ? 0.2 : hovered ? 1 : 0.9;
    context.stroke(path);
    context.globalAlpha = 1;
    drawSolderPad(start, color, hovered, muted);
    drawSolderPad(end, color, hovered, muted);
    app.wirePaths.push({
      id,
      type: "signal",
      index,
      path,
      connection,
      start,
      end,
      route: routeControlPoint(start, end, route),
      routeStyle: route.style,
      hitPoint: longestSegmentMidpoint(points),
      color,
    });
  });
  if (app.selectedWireId === "ground-bus") drawGroundNetwork(grounds);
  if (app.interactionMode === "layout") {
    for (const wire of app.wirePaths) {
      drawRouteHandle(wire.route, wire.color || colors.black, app.selectedWireId === wire.id);
    }
  }
  const selected = app.wirePaths.find((wire) => wire.id === app.selectedWireId);
  if (selected?.type === "signal") {
    drawSolderPad(selected.start, selected.color, true, false);
    drawSolderPad(selected.end, selected.color, true, false);
    drawPinLabel(selected.start, selected.connection[0], selected.color);
    drawPinLabel(selected.end, selected.connection[1], selected.color);
  }
}

function isGroundConnection(connection) {
  return (app.config?.wiring?.groundConnectionIds || []).includes(connectionId(connection));
}

function drawGroundNetwork(connections) {
  const switchPart = app.diagram.parts.find((part) => part.id === "link");
  const defaultBusY = switchPart
    ? (switchPart.top || 0) - 4
    : canvasPosition(0, canvas.getBoundingClientRect().height - 40).y;
  const busY = worldPosition(0, app.groundBusY ?? defaultBusY).y;
  const endpoints = new Map();
  for (const connection of connections) {
    for (const reference of connection.slice(0, 2)) {
      const point = pinPoint(reference);
      if (!point) continue;
      const key = `${Math.round(point.x)}:${Math.round(point.y)}`;
      endpoints.set(key, { point, reference });
    }
  }
  const nodes = [...endpoints.values()];
  if (!nodes.length) return;
  const minX = Math.min(...nodes.map((node) => node.point.x)) - 8 * app.scale;
  const maxX = Math.max(...nodes.map((node) => node.point.x)) + 8 * app.scale;
  context.strokeStyle = colors.black;
  const selected = app.selectedWireId === "ground-bus";
  const muted = Boolean(app.selectedWireId && !selected);
  context.lineWidth = Math.max(selected ? 4 : 2, (selected ? 4 : 2.4) * app.scale);
  context.globalAlpha = muted ? 0.2 : 0.9;
  context.beginPath();
  context.moveTo(minX, busY);
  context.lineTo(maxX, busY);
  context.stroke();
  const busPath = new Path2D();
  busPath.moveTo(minX, busY);
  busPath.lineTo(maxX, busY);
  for (const { point } of nodes) {
    context.beginPath();
    context.moveTo(point.x, point.y);
    context.lineTo(point.x, busY);
    context.stroke();
    drawSolderPad(point, colors.black, selected, muted);
  }
  context.globalAlpha = 1;
  app.wirePaths.push({
    id: "ground-bus",
    type: "ground-bus",
    path: busPath,
    nodes,
    route: { x: (minX + maxX) / 2, y: busY },
    hitPoint: { x: (minX + maxX) / 2, y: busY },
    color: colors.black,
  });
  if (selected) {
    const boardGround = nodes.find((node) => (app.config?.wiring?.groundPins || []).includes(node.reference));
    if (boardGround) drawPinLabel(boardGround.point, boardGround.reference, colors.black);
  }
}

function drawSolderPad(point, color, highlighted, muted = false) {
  overlayContext.save();
  overlayContext.globalAlpha = muted ? 0.25 : 1;
  overlayContext.shadowColor = highlighted ? color : "transparent";
  overlayContext.shadowBlur = highlighted ? 8 : 0;
  overlayContext.beginPath();
  overlayContext.arc(point.x, point.y, highlighted ? 7 : 5, 0, Math.PI * 2);
  overlayContext.fillStyle = "#111412";
  overlayContext.fill();
  overlayContext.lineWidth = highlighted ? 2.5 : 1.8;
  overlayContext.strokeStyle = "#f4f7f5";
  overlayContext.stroke();
  overlayContext.shadowBlur = 0;
  overlayContext.beginPath();
  overlayContext.arc(point.x, point.y, highlighted ? 4.2 : 3, 0, Math.PI * 2);
  overlayContext.lineWidth = highlighted ? 3 : 2;
  overlayContext.strokeStyle = color;
  overlayContext.stroke();
  overlayContext.restore();
}

function drawRouteHandle(point, color, selected) {
  overlayContext.save();
  overlayContext.translate(point.x, point.y);
  overlayContext.rotate(Math.PI / 4);
  const size = selected ? 9 : 7;
  overlayContext.fillStyle = selected ? color : "#111412";
  overlayContext.fillRect(-size / 2, -size / 2, size, size);
  overlayContext.lineWidth = selected ? 2.5 : 1.5;
  overlayContext.strokeStyle = selected ? "#f4f7f5" : color;
  overlayContext.strokeRect(-size / 2, -size / 2, size, size);
  overlayContext.restore();
}

function validateWiring() {
  const wiring = app.config?.wiring || {};
  const expected = new Set((wiring.expectedConnections || []).map(([start, end]) => `${start}>${end}`));
  const actual = new Set(app.diagram.connections.map(connectionId));
  const errors = [];
  for (const id of expected) if (!actual.has(id)) errors.push(`Missing ${id}`);
  for (const id of actual) if (!expected.has(id)) errors.push(`Unexpected ${id}`);
  const boardUsage = new Map();
  for (const connection of app.diagram.connections) {
    for (const reference of connection.slice(0, 2)) {
      const [partId] = reference.split(":");
      if (!(wiring.boardPartIds || []).includes(partId) || (wiring.sharedPins || []).includes(reference)) continue;
      boardUsage.set(reference, (boardUsage.get(reference) || 0) + 1);
    }
  }
  for (const [reference, count] of boardUsage) {
    if (count > 1) errors.push(`Duplicate ${reference}`);
  }
  const powerPins = wiring.powerPins || [];
  const groundPins = wiring.groundPins || [];
  const powerConnections = app.diagram.connections.filter(connection =>
    connection.some(reference => powerPins.includes(reference) || groundPins.includes(reference)));
  for (const connection of powerConnections) {
    if (connection.some(reference => powerPins.includes(reference))
      && connection.some(reference => groundPins.includes(reference))) {
      errors.push("Power shorted to ground");
    }
  }
  return errors;
}

function updateWiringPanel() {
  const selected = app.wirePaths.find((wire) => wire.id === app.selectedWireId);
  const hoveredId = app.hoveredWire;
  document.querySelectorAll("[data-wire-id]").forEach((row) => {
    const active = row.dataset.wireId === app.selectedWireId;
    row.classList.toggle("active", active);
    row.classList.toggle("hovered", row.dataset.wireId === hoveredId);
    row.classList.toggle("muted", Boolean(app.selectedWireId && !active));
    if (active) row.style.setProperty("--row-color", selected?.color || colors.black);
  });
  const trace = document.getElementById("wireTrace");
  if (!selected) {
    trace.className = "wire-trace";
    trace.style.removeProperty("--trace-color");
    trace.innerHTML = `<span>${app.config?.wiring?.emptyTrace || "Select a wire or solder pad"}</span>`;
  } else if (selected.type === "ground-bus") {
    trace.className = "wire-trace active";
    trace.style.setProperty("--trace-color", colors.black);
    const groundTrace = app.config?.wiring?.groundTrace || "ALL RETURNS → GND";
    const [left, right = "GND"] = groundTrace.split("→").map(value => value.trim());
    trace.innerHTML = `<b>${left}</b> &rarr; ${right}`;
  } else {
    trace.className = "wire-trace active";
    trace.style.setProperty("--trace-color", selected.color);
    trace.innerHTML = `<b>${formatPinReference(selected.connection[0])}</b> &rarr; ${formatPinReference(selected.connection[1])}`;
  }
  const errors = validateWiring();
  const badge = document.getElementById("wiringValidation");
  badge.className = `validation-badge ${errors.length ? "invalid" : "valid"}`;
  badge.textContent = errors.length ? `${errors.length} issues` : "Wiring valid";
  badge.title = errors.join("\n") || app.config?.wiring?.validTitle || "Expected connections and power rails are valid.";
}

function formatPinReference(reference) {
  const [id, pin] = reference.split(":");
  const part = app.diagram.parts.find((candidate) => candidate.id === id);
  const exact = app.config?.wiring?.referenceLabels?.[reference];
  if (exact) return exact;
  const label = app.config?.wiring?.partLabels?.[id] || part?.attrs?.label || id.toUpperCase();
  return `${label} · ${pin}`;
}

function drawPinLabel(point, reference, color) {
  overlayContext.save();
  const text = formatPinReference(reference);
  overlayContext.font = "700 10px ui-monospace, SFMono-Regular, Menlo, monospace";
  const width = overlayContext.measureText(text).width + 12;
  const canvasWidth = canvas.getBoundingClientRect().width;
  const partId = reference.split(":")[0];
  const partBounds = app.partElements.get(partId)?.wrapper.getBoundingClientRect();
  const canvasBounds = canvas.getBoundingClientRect();
  const partCenterX = partBounds
    ? partBounds.left - canvasBounds.left + partBounds.width / 2
    : canvasWidth / 2;
  const x = point.x >= partCenterX
    ? Math.min(point.x + 10, canvasWidth - width - 4)
    : Math.max(4, point.x - width - 10);
  const y = Math.max(4, point.y - 22);
  overlayContext.fillStyle = "rgba(10, 12, 11, 0.96)";
  overlayContext.fillRect(x, y, width, 18);
  overlayContext.lineWidth = 1.5;
  overlayContext.strokeStyle = color;
  overlayContext.strokeRect(x, y, width, 18);
  overlayContext.fillStyle = "#f4f7f5";
  overlayContext.textAlign = "left";
  overlayContext.fillText(text, x + 6, y + 12.5);
  overlayContext.restore();
}

function layoutPartElements() {
  for (const part of app.diagram.parts) {
    if (part.type === "wokwi-text") continue;
    updatePartElement(part, worldPoint(part, 0, 0), partSize(part));
  }
}

function drawTextParts() {
  for (const part of app.diagram.parts) {
    if (part.type !== "wokwi-text") continue;
    const point = worldPoint(part, 0, 0);
    context.save();
    context.translate(point.x, point.y);
    context.scale(app.scale, app.scale);
    drawText(part);
    context.restore();
  }
}

function updateHitAreas() {
  const canvasBounds = canvas.getBoundingClientRect();
  app.hitAreas = app.diagram.parts
    .filter((part) => part.type !== "wokwi-text")
    .map((part) => {
      const bounds = app.partElements.get(part.id)?.wrapper.getBoundingClientRect();
      if (!bounds) return null;
      return {
        part,
        x: bounds.left - canvasBounds.left,
        y: bounds.top - canvasBounds.top,
        width: bounds.width,
        height: bounds.height,
      };
    })
    .filter(Boolean);
}

function createPartElements() {
  partsLayer.replaceChildren();
  app.partElements.clear();
  for (const part of app.diagram.parts) {
    if (part.type === "wokwi-text") continue;
    const wrapper = document.createElement("div");
    wrapper.className = "circuit-part";
    wrapper.dataset.partId = part.id;
    let element;
    const board = app.config?.boards?.[part.type];
    if (board) {
      element = document.createElement("img");
      element.src = board.asset;
      element.alt = "";
    } else {
      element = document.createElement(part.type);
      for (const [name, value] of Object.entries(part.attrs || {})) element.setAttribute(name, value);
    }
    wrapper.appendChild(element);
    if (app.config?.orientations?.[part.id]) {
      const orientation = document.createElement("span");
      orientation.className = "orientation-badge";
      wrapper.appendChild(orientation);
      visualOrientationText(part, orientation);
    }
    partsLayer.appendChild(wrapper);
    const visual = { wrapper, element, pinGeometry: null };
    app.partElements.set(part.id, visual);
    if (!board) {
      requestAnimationFrame(() => {
        const svg = element.shadowRoot?.querySelector("svg");
        if (!svg) return;
        const width = svg.width.baseVal.value;
        const height = svg.height.baseVal.value;
        visual.pinGeometry = {
          width,
          height,
          svg,
          pins: new Map((element.pinInfo || []).map((item) => [item.name, item])),
        };
        const overlayCanvas = element.shadowRoot?.querySelector("canvas");
        if (overlayCanvas && svg.parentElement) {
          visual.shadowScaleContainer = svg.parentElement;
          visual.shadowScaleContainer.style.width = `${width}px`;
          visual.shadowScaleContainer.style.height = `${height}px`;
          visual.shadowScaleContainer.style.transformOrigin = "top left";
        } else {
          svg.style.width = "100%";
          svg.style.height = "100%";
        }
        updateDisplays();
        draw();
      });
    }
  }
}

function updatePartElement(part, point, size) {
  const visual = app.partElements.get(part.id);
  if (!visual) return;
  visual.wrapper.style.left = `${point.x}px`;
  visual.wrapper.style.top = `${point.y}px`;
  visual.wrapper.style.width = `${size.width * app.scale}px`;
  visual.wrapper.style.height = `${size.height * app.scale}px`;
  if (visual.shadowScaleContainer && visual.pinGeometry) {
    visual.shadowScaleContainer.style.transform = `scale(${size.width * app.scale / visual.pinGeometry.width}, ${size.height * app.scale / visual.pinGeometry.height})`;
  }
  visual.wrapper.style.transform = part.rotate ? `rotate(${part.rotate}deg)` : "none";
  const orientation = visual.wrapper.querySelector(".orientation-badge");
  if (orientation) visualOrientationText(part, orientation);

  const control = controlFor(part);
  if (control?.kind === "momentary") {
    visual.element.pressed = Boolean(getPath(app.state, control.statePath));
  } else if (control?.kind === "toggle") {
    visual.element.value = getPath(app.state, control.statePath) ? 1 : 0;
  } else if (control?.kind === "indicator") {
    visual.element.value = getPath(app.state, control.statePath) ? 1 : 0;
  }
  for (const rule of control?.classes || []) {
    visual.wrapper.classList.toggle(rule.name, matchesRule(rule));
  }
}

function visualOrientationText(part, element) {
  const angle = ((part.rotate || 0) % 360 + 360) % 360;
  element.textContent = `${app.config?.orientations?.[part.id] || "FRONT"} · ${angle}°`;
}

function routingObstacles() {
  const canvasBounds = canvas.getBoundingClientRect();
  return app.diagram.parts.map((part) => {
    if (part.type === "wokwi-text") {
      const bounds = partBounds(part);
      const topLeft = worldPosition(bounds.left, bounds.top);
      return {
        id: part.id,
        left: topLeft.x - 10,
        top: topLeft.y - 8,
        right: topLeft.x + (bounds.right - bounds.left) * app.scale + 10,
        bottom: topLeft.y + (bounds.bottom - bounds.top) * app.scale + 8,
      };
    }
    const bounds = app.partElements.get(part.id)?.wrapper.getBoundingClientRect();
    if (!bounds) return null;
    return {
      id: part.id,
      left: bounds.left - canvasBounds.left - 14,
      top: bounds.top - canvasBounds.top - 14,
      right: bounds.right - canvasBounds.left + 14,
      bottom: bounds.bottom - canvasBounds.top + 14,
    };
  }).filter(Boolean);
}

function segmentIntersectsRect(segment, rect) {
  const minX = Math.min(segment.start.x, segment.end.x);
  const maxX = Math.max(segment.start.x, segment.end.x);
  const minY = Math.min(segment.start.y, segment.end.y);
  const maxY = Math.max(segment.start.y, segment.end.y);
  return maxX >= rect.left && minX <= rect.right && maxY >= rect.top && minY <= rect.bottom;
}

function segmentsCross(left, right) {
  const leftVertical = Math.abs(left.start.x - left.end.x) < 0.5;
  const rightVertical = Math.abs(right.start.x - right.end.x) < 0.5;
  if (leftVertical === rightVertical) {
    if (leftVertical && Math.abs(left.start.x - right.start.x) < 0.5) {
      return Math.max(Math.min(left.start.y, left.end.y), Math.min(right.start.y, right.end.y))
        <= Math.min(Math.max(left.start.y, left.end.y), Math.max(right.start.y, right.end.y));
    }
    if (!leftVertical && Math.abs(left.start.y - right.start.y) < 0.5) {
      return Math.max(Math.min(left.start.x, left.end.x), Math.min(right.start.x, right.end.x))
        <= Math.min(Math.max(left.start.x, left.end.x), Math.max(right.start.x, right.end.x));
    }
    return false;
  }
  const vertical = leftVertical ? left : right;
  const horizontal = leftVertical ? right : left;
  return vertical.start.x >= Math.min(horizontal.start.x, horizontal.end.x)
    && vertical.start.x <= Math.max(horizontal.start.x, horizontal.end.x)
    && horizontal.start.y >= Math.min(vertical.start.y, vertical.end.y)
    && horizontal.start.y <= Math.max(vertical.start.y, vertical.end.y);
}

function routeScore(points, obstacles, startPartId, endPartId, routedSegments, bounds) {
  const segments = routeSegments(points);
  let score = segments.reduce(
    (total, segment) => total + Math.hypot(segment.end.x - segment.start.x, segment.end.y - segment.start.y),
    0,
  );
  segments.forEach((segment, segmentIndex) => {
    for (const obstacle of obstacles) {
      if (obstacle.id === startPartId && segmentIndex === 0) continue;
      if (obstacle.id === endPartId && segmentIndex === segments.length - 1) continue;
      if (segmentIntersectsRect(segment, obstacle)) score += 100000;
    }
    for (const routed of routedSegments) if (segmentsCross(segment, routed)) score += 220;
    if (Math.min(segment.start.x, segment.end.x) < 16
      || Math.max(segment.start.x, segment.end.x) > bounds.width - 16
      || Math.min(segment.start.y, segment.end.y) < 16
      || Math.max(segment.start.y, segment.end.y) > bounds.height - 16) score += 10000;
  });
  return score;
}

async function autoRoute() {
  layoutPartElements();
  updateHitAreas();
  const bounds = canvas.getBoundingClientRect();
  const obstacles = routingObstacles();
  const xCandidates = new Set([24, bounds.width - 24]);
  const yCandidates = new Set([24, bounds.height - 24]);
  for (const obstacle of obstacles) {
    xCandidates.add(obstacle.left - 12);
    xCandidates.add(obstacle.right + 12);
    yCandidates.add(obstacle.top - 12);
    yCandidates.add(obstacle.bottom + 12);
  }
  const routedSegments = [];
  const nextRoutes = {};
  const signals = app.diagram.connections.filter(connection => !isGroundConnection(connection));
  for (const connection of signals) {
    const start = pinPoint(connection[0]);
    const end = pinPoint(connection[1]);
    if (!start || !end) continue;
    const localXs = new Set([...xCandidates, start.x, end.x, (start.x + end.x) / 2]);
    const localYs = new Set([...yCandidates, start.y, end.y, (start.y + end.y) / 2]);
    let best = null;
    const startPartId = connection[0].split(":")[0];
    const endPartId = connection[1].split(":")[0];
    for (const x of localXs) {
      const route = { x, y: (start.y + end.y) / 2, style: "hv" };
      const points = routedPoints(start, end, route);
      const score = routeScore(points, obstacles, startPartId, endPartId, routedSegments, bounds);
      if (!best || score < best.score) best = { route, points, score };
    }
    for (const y of localYs) {
      const route = { x: (start.x + end.x) / 2, y, style: "vh" };
      const points = routedPoints(start, end, route);
      const score = routeScore(points, obstacles, startPartId, endPartId, routedSegments, bounds);
      if (!best || score < best.score) best = { route, points, score };
    }
    if (!best) continue;
    nextRoutes[connectionId(connection)] = {
      ...canvasPosition(best.route.x, best.route.y),
      style: best.route.style,
    };
    routedSegments.push(...routeSegments(best.points));
  }
  const movableBounds = app.diagram.parts
    .filter(part => part.type !== "wokwi-text")
    .map(partBounds);
  app.wireRoutes = nextRoutes;
  app.groundBusY = Math.max(...movableBounds.map(item => item.bottom)) + 24;
  draw();
  await saveLayout();
  fitCircuit();
}

function roundedRect(x, y, width, height, radius) {
  context.beginPath();
  context.roundRect(x, y, width, height, radius);
}

function drawBoard(size) {
  roundedRect(0, 0, size.width, size.height, 7);
  context.fillStyle = "#252a27";
  context.fill();
  context.strokeStyle = "#616963";
  context.stroke();
  roundedRect(14, 13, size.width - 28, 48, 4);
  context.fillStyle = "#313733";
  context.fill();
  context.fillStyle = "#aeb6b0";
  context.font = "700 7px ui-monospace, monospace";
  context.textAlign = "center";
  context.fillText("XIAO ESP32-S3", size.width / 2, 35);
  context.fillStyle = "#4f5751";
  context.fillRect(33, 81, 40, 52);
  context.fillStyle = "#111312";
  context.fillRect(42, 91, 22, 31);
  context.fillStyle = "#c6ccc7";
  context.fillRect(33, 151, 40, 25);
  context.fillStyle = "#d7b85a";
  for (let y = 18; y < size.height - 12; y += 14) {
    context.fillRect(-3, y, 7, 5);
    context.fillRect(size.width - 4, y, 7, 5);
  }
}

function fingerIndex(id) {
  return { touch1: 0, touch2: 1, touch3: 2, little: 3 }[id];
}

function drawButton(part, size) {
  const index = fingerIndex(part.id);
  const down = part.id === "thumb" ? app.state?.thumb : app.state?.fingers?.[index];
  roundedRect(3, 3, size.width - 6, size.height - 6, 5);
  context.fillStyle = "#d4d9d5";
  context.fill();
  context.strokeStyle = "#6c746e";
  context.stroke();
  context.beginPath();
  context.arc(size.width / 2, size.height / 2 - 2, 17, 0, Math.PI * 2);
  context.fillStyle = part.id === "thumb" ? (down ? "#ffaaa5" : "#e85650") : (down ? "#8ee4ff" : "#168ec1");
  context.fill();
  context.strokeStyle = down ? "#ffffff" : "#172019";
  context.lineWidth = 2;
  context.stroke();
  context.fillStyle = "#aeb6b0";
  context.font = "700 7px ui-monospace, monospace";
  context.textAlign = "center";
  context.fillText(part.attrs?.label || part.id, size.width / 2, size.height + 12);
}

function drawSwitch(part, size) {
  const connected = Boolean(app.state?.connected);
  roundedRect(0, 4, size.width, size.height - 8, 7);
  context.fillStyle = "#303632";
  context.fill();
  context.strokeStyle = connected ? "#6dff9d" : "#636b65";
  context.stroke();
  roundedRect(connected ? size.width - 33 : 5, 9, 28, size.height - 18, 5);
  context.fillStyle = connected ? "#58d986" : "#8c938d";
  context.fill();
  context.fillStyle = connected ? "#6dff9d" : "#aeb6b0";
  context.font = "700 7px ui-monospace, monospace";
  context.textAlign = "center";
  context.fillText(connected ? "LINK ON" : "LINK OFF", size.width / 2, size.height + 11);
}

function drawImu(size) {
  roundedRect(0, 0, size.width, size.height, 4);
  context.fillStyle = "#245b87";
  context.fill();
  context.strokeStyle = "#65b8f2";
  context.stroke();
  context.fillStyle = "#18211d";
  context.fillRect(33, 17, 38, 38);
  context.fillStyle = "#d9e0da";
  context.font = "700 8px ui-monospace, monospace";
  context.textAlign = "center";
  context.fillText("MPU6050", size.width / 2, 69);
}

function drawLed(size) {
  const active = Boolean(app.state?.bits !== "0000" || app.state?.thumb);
  context.beginPath();
  context.arc(size.width / 2, 18, 13, 0, Math.PI * 2);
  context.fillStyle = active ? "#6dff9d" : "#274a34";
  context.shadowColor = active ? "#6dff9d" : "transparent";
  context.shadowBlur = active ? 16 : 0;
  context.fill();
  context.shadowBlur = 0;
  context.fillStyle = "#aeb6b0";
  context.font = "700 7px ui-monospace, monospace";
  context.textAlign = "center";
  context.fillText("STATUS", size.width / 2, 54);
}

function drawResistor(size) {
  context.strokeStyle = "#8a918b";
  context.beginPath();
  context.moveTo(0, size.height / 2);
  context.lineTo(12, size.height / 2);
  context.lineTo(17, 4);
  context.lineTo(25, 16);
  context.lineTo(33, 4);
  context.lineTo(41, 16);
  context.lineTo(size.width, size.height / 2);
  context.stroke();
}

function drawText(part) {
  context.fillStyle = "#dfe5e0";
  context.font = "700 13px ui-sans-serif, sans-serif";
  context.fillText(part.attrs?.text || "", 0, 18);
}

function hitPart(event) {
  const bounds = canvas.getBoundingClientRect();
  const x = event.clientX - bounds.left;
  const y = event.clientY - bounds.top;
  return [...app.hitAreas].reverse().find(
    (area) => x >= area.x && x <= area.x + area.width && y >= area.y && y <= area.y + area.height,
  )?.part;
}

function hitWires(event) {
  const bounds = canvas.getBoundingClientRect();
  const x = event.clientX - bounds.left;
  const y = event.clientY - bounds.top;
  const candidates = [];
  if (app.interactionMode === "layout") {
    const handles = app.wirePaths
      .map((wire) => ({ wire, distance: Math.hypot(wire.route.x - x, wire.route.y - y) }))
      .filter(({ distance }) => distance <= 11)
      .sort((left, right) => left.distance - right.distance);
    candidates.push(...handles.map(({ wire }) => wire));
  }
  context.save();
  context.setTransform(1, 0, 0, 1, 0, 0);
  context.lineWidth = app.interactionMode === "layout" ? 18 : 12;
  for (const wire of app.wirePaths) {
    if (context.isPointInStroke(wire.path, x, y) && !candidates.includes(wire)) candidates.push(wire);
  }
  context.restore();
  return candidates;
}

function hitSolderPad(event) {
  const bounds = canvas.getBoundingClientRect();
  const point = { x: event.clientX - bounds.left, y: event.clientY - bounds.top };
  const candidates = [];
  for (const wire of app.wirePaths) {
    const endpoints = wire.type === "ground-bus"
      ? wire.nodes.map((node) => node.point)
      : [wire.start, wire.end];
    for (const endpoint of endpoints) {
      candidates.push({ wire, distance: Math.hypot(endpoint.x - point.x, endpoint.y - point.y) });
    }
  }
  return candidates
    .filter(({ distance }) => distance <= 9)
    .sort((left, right) => {
      const selectedOrder = Number(right.wire.id === app.selectedWireId)
        - Number(left.wire.id === app.selectedWireId);
      return selectedOrder || left.distance - right.distance;
    })[0]?.wire || null;
}

function hitWireHandle(event) {
  if (app.interactionMode !== "layout") return null;
  const bounds = canvas.getBoundingClientRect();
  const x = event.clientX - bounds.left;
  const y = event.clientY - bounds.top;
  return app.wirePaths
    .map((wire) => ({ wire, distance: Math.hypot(wire.route.x - x, wire.route.y - y) }))
    .filter(({ distance }) => distance <= 11)
    .sort((left, right) => {
      const selectedOrder = Number(right.wire.id === app.selectedWireId)
        - Number(left.wire.id === app.selectedWireId);
      return selectedOrder || left.distance - right.distance;
    })[0]?.wire || null;
}

function hitWire(event, cycle = false) {
  const candidates = hitWires(event);
  if (!candidates.length) return null;
  const selectedIndex = candidates.findIndex((wire) => wire.id === app.selectedWireId);
  if (selectedIndex >= 0) {
    if (!cycle) return candidates[selectedIndex];
    const bounds = canvas.getBoundingClientRect();
    const selected = candidates[selectedIndex];
    const onSelectedHandle = Math.hypot(
      selected.route.x - (event.clientX - bounds.left),
      selected.route.y - (event.clientY - bounds.top),
    ) <= 11;
    return onSelectedHandle ? selected : candidates[(selectedIndex + 1) % candidates.length];
  }
  return candidates[0];
}

function pointerPayload(part, down) {
  const control = controlFor(part);
  if (!control) return null;
  if (control.kind === "momentary") return { ...(down ? control.press : control.release) };
  if (control.kind === "toggle") {
    return { ...(getPath(app.state, control.statePath) ? control.off : control.on) };
  }
  return null;
}

function isInteractivePart(part) {
  return ["momentary", "toggle"].includes(controlFor(part)?.kind);
}

function layoutPayload() {
  return {
    parts: Object.fromEntries(
      app.diagram.parts
        .filter((part) => part.type !== "wokwi-text")
        .map((part) => [part.id, {
          left: part.left || 0,
          top: part.top || 0,
          rotate: (part.rotate || 0) % 360,
        }]),
    ),
    wires: app.wireRoutes,
    groundBusY: app.groundBusY,
  };
}

function saveLayout() {
  const request = app.layoutQueue.then(() => api("/api/layout", {
    method: "POST",
    body: JSON.stringify(layoutPayload()),
  }));
  app.layoutQueue = request.catch((error) => console.error(error));
  return request;
}

function applySavedRoutes() {
  app.wireRoutes = { ...(app.diagram.layout?.wires || {}) };
  app.groundBusY = app.diagram.layout?.groundBusY ?? null;
  app.defaultRouteScheduled = false;
}

function scheduleDefaultRouting() {
  if (app.defaultRouteScheduled || Object.keys(app.wireRoutes).length) return;
  app.defaultRouteScheduled = true;
  let attempts = 0;
  const run = async () => {
    if (app.unloading || Object.keys(app.wireRoutes).length) {
      app.defaultRouteScheduled = false;
      return;
    }
    const anchorsReady = app.diagram.connections.every(
      connection => pinPoint(connection[0]) && pinPoint(connection[1]),
    );
    if (!anchorsReady && attempts < 40) {
      attempts += 1;
      window.setTimeout(run, 50);
      return;
    }
    app.defaultRouteScheduled = false;
    if (anchorsReady) await autoRoute();
  };
  window.setTimeout(run, 50);
}

async function releaseRunInputs() {
  if (app.pointerPart && controlFor(app.pointerPart)?.kind === "momentary") {
    const payload = pointerPayload(app.pointerPart, false);
    if (payload) await sendInput(payload);
  }
  app.pointerPart = null;
  for (const code of heldKeyboardCodes) {
    const part = app.diagram.parts.find(candidate => candidate.id === keyboardBindings.get(code));
    const payload = pointerPayload(part, false);
    if (payload) await sendInput(payload);
  }
  heldKeyboardCodes.clear();
}

async function setInteractionMode(mode) {
  if (!['run', 'layout'].includes(mode) || mode === app.interactionMode) return;
  if (mode === "layout") await releaseRunInputs();
  app.interactionMode = mode;
  if (mode === "run") clearSelection();
  document.body.classList.toggle("layout-mode", mode === "layout");
  document.querySelectorAll("[data-interaction-mode]").forEach((button) => {
    const active = button.dataset.interactionMode === mode;
    button.classList.toggle("active", active);
    button.setAttribute("aria-pressed", String(active));
  });
  canvas.style.cursor = "default";
  draw();
}

function selectPart(part) {
  app.selectedPartId = part?.id || null;
  app.selectedWireId = null;
  app.partElements.forEach((visual, partId) => {
    visual.wrapper.classList.toggle("selected", partId === app.selectedPartId);
  });
  const enabled = app.interactionMode === "layout" && Boolean(app.selectedPartId);
  document.getElementById("rotateLeftButton").disabled = !enabled;
  document.getElementById("rotateRightButton").disabled = !enabled;
}

function selectWire(wire) {
  app.selectedPartId = null;
  app.selectedWireId = wire?.id || null;
  app.partElements.forEach((visual) => visual.wrapper.classList.remove("selected"));
  document.getElementById("rotateLeftButton").disabled = true;
  document.getElementById("rotateRightButton").disabled = true;
  draw();
}

function clearSelection() {
  selectPart(null);
}

async function rotateSelected(delta) {
  const part = app.diagram.parts.find((candidate) => candidate.id === app.selectedPartId);
  if (!part || app.interactionMode !== "layout") return;
  part.rotate = ((part.rotate || 0) + delta + 360) % 360;
  draw();
  await saveLayout();
}

canvas.addEventListener("pointerdown", async (event) => {
  const routeHandleWire = hitWireHandle(event);
  const selectedHandleWire = routeHandleWire?.id === app.selectedWireId ? routeHandleWire : null;
  const padWire = selectedHandleWire ? null : hitSolderPad(event);
  const handleWire = selectedHandleWire || padWire || routeHandleWire;
  const part = handleWire ? null : hitPart(event);
  if (!part) {
    const wire = handleWire || hitWire(event, true);
    if (app.interactionMode === "layout") {
      if (!wire) {
        clearSelection();
        draw();
        return;
      }
      event.preventDefault();
      canvas.setPointerCapture(event.pointerId);
      selectWire(wire);
      const routeWorld = canvasPosition(wire.route.x, wire.route.y);
      const savedRoute = wire.type === "signal" ? app.wireRoutes[wire.id] : null;
      app.wireDrag = {
        wire,
        startX: event.clientX,
        startY: event.clientY,
        startRoute: { ...routeWorld },
        originalRoute: savedRoute ? { ...savedRoute } : null,
        originalGroundBusY: app.groundBusY,
      };
      canvas.style.cursor = "move";
    } else if (wire) {
      selectWire(wire);
    } else {
      clearSelection();
      draw();
    }
    return;
  }
  event.preventDefault();
  canvas.setPointerCapture(event.pointerId);
  if (app.interactionMode === "layout") {
    selectPart(part);
    app.hoveredWire = null;
    app.drag = {
      part,
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      startLeft: part.left || 0,
      startTop: part.top || 0,
    };
    app.partElements.get(part.id)?.wrapper.classList.add("dragging");
    canvas.style.cursor = "grabbing";
    return;
  }
  if (!isInteractivePart(part)) return;
  app.pointerPart = part;
  await sendInput(pointerPayload(part, true));
});

canvas.addEventListener("pointermove", (event) => {
  if (app.wireDrag) {
    const { wire, startX, startY, startRoute } = app.wireDrag;
    const nextRoute = {
      x: startRoute.x + (event.clientX - startX) / app.scale,
      y: startRoute.y + (event.clientY - startY) / app.scale,
    };
    if (wire.type === "ground-bus") {
      app.groundBusY = nextRoute.y;
    } else {
      app.wireRoutes[wire.id] = {
        ...nextRoute,
        ...(wire.routeStyle ? { style: wire.routeStyle } : {}),
      };
    }
    draw();
    return;
  }
  if (app.drag) {
    const { part, startX, startY, startLeft, startTop } = app.drag;
    part.left = startLeft + (event.clientX - startX) / app.scale;
    part.top = startTop + (event.clientY - startY) / app.scale;
    draw();
    return;
  }
  if (app.pointerPart) return;
  const part = hitPart(event);
  if (app.interactionMode === "layout") {
    const wire = part ? null : hitWire(event);
    canvas.style.cursor = part ? "grab" : wire ? "move" : "default";
    return;
  }
  const hoveredWire = hitWire(event);
  if (hoveredWire?.id === app.hoveredWire) return;
  app.hoveredWire = hoveredWire?.id || null;
  canvas.style.cursor = hoveredWire || isInteractivePart(part) ? "pointer" : "default";
  draw();
});

canvas.addEventListener("pointerleave", () => {
  if (app.drag || app.wireDrag) return;
  if (!app.hoveredWire) return;
  app.hoveredWire = null;
  canvas.style.cursor = "default";
  draw();
});

canvas.addEventListener("pointerup", async (event) => {
  if (app.wireDrag) {
    app.wireDrag = null;
    canvas.style.cursor = "move";
    await saveLayout();
    return;
  }
  if (app.drag) {
    const { part } = app.drag;
    app.drag = null;
    app.partElements.get(part.id)?.wrapper.classList.remove("dragging");
    canvas.style.cursor = "grab";
    await saveLayout();
    return;
  }
  if (!app.pointerPart) return;
  const part = app.pointerPart;
  app.pointerPart = null;
  if (controlFor(part)?.kind === "momentary") await sendInput(pointerPayload(part, false));
});

canvas.addEventListener("pointercancel", async () => {
  if (app.wireDrag) {
    const { wire, originalRoute, originalGroundBusY } = app.wireDrag;
    if (wire.type === "ground-bus") {
      app.groundBusY = originalGroundBusY;
    } else if (originalRoute) {
      app.wireRoutes[wire.id] = originalRoute;
    } else {
      delete app.wireRoutes[wire.id];
    }
    app.wireDrag = null;
    canvas.style.cursor = "default";
    draw();
    return;
  }
  if (app.drag) {
    const { part, startLeft, startTop } = app.drag;
    part.left = startLeft;
    part.top = startTop;
    app.drag = null;
    app.partElements.get(part.id)?.wrapper.classList.remove("dragging");
    canvas.style.cursor = "default";
    draw();
    return;
  }
  if (!app.pointerPart || controlFor(app.pointerPart)?.kind !== "momentary") return;
  const part = app.pointerPart;
  app.pointerPart = null;
  await sendInput(pointerPayload(part, false));
});

document.addEventListener("keydown", (event) => {
  const partId = keyboardBindings.get(event.code);
  if (!partId) return;
  if (app.interactionMode !== "run") return;
  event.preventDefault();
  if (event.repeat || heldKeyboardCodes.has(event.code)) return;
  heldKeyboardCodes.add(event.code);
  const part = app.diagram.parts.find(candidate => candidate.id === partId);
  const payload = pointerPayload(part, true);
  if (payload) void sendInput(payload);
});

document.addEventListener("keyup", (event) => {
  const partId = keyboardBindings.get(event.code);
  if (!partId) return;
  if (app.interactionMode !== "run") return;
  event.preventDefault();
  if (!heldKeyboardCodes.delete(event.code)) return;
  const part = app.diagram.parts.find(candidate => candidate.id === partId);
  const payload = pointerPayload(part, false);
  if (payload) void sendInput(payload);
});

window.addEventListener("blur", () => {
  if (app.interactionMode !== "run") return;
  for (const code of heldKeyboardCodes) {
    const part = app.diagram.parts.find(candidate => candidate.id === keyboardBindings.get(code));
    const payload = pointerPayload(part, false);
    if (payload) void sendInput(payload);
  }
  heldKeyboardCodes.clear();
});

function updateStatus() {
  if (!app.state) return;
  document.querySelectorAll("[data-state-path]").forEach((element) => {
    const raw = getPath(app.state, element.dataset.statePath, "");
    const labels = element.dataset.labels ? JSON.parse(element.dataset.labels) : null;
    const value = labels?.[String(raw)] ?? raw;
    element.textContent = element.dataset.template
      ? interpolate(element.dataset.template)
      : String(value);
    element.classList.toggle("active", Boolean(raw));
  });
  document.querySelectorAll("[data-badge-path]").forEach((element) => {
    const raw = getPath(app.state, element.dataset.badgePath, "");
    const labels = JSON.parse(element.dataset.labels || "{}");
    const tones = JSON.parse(element.dataset.tones || "{}");
    element.textContent = labels[String(raw)] ?? raw;
    element.className = `${element.dataset.baseClass || "badge"} ${tones[String(raw)] || ""}`.trim();
  });
  document.querySelectorAll("[data-progress-path]").forEach((element) => {
    const value = Number(getPath(app.state, element.dataset.progressPath, 0));
    const max = Number(getPath(app.state, element.dataset.progressMaxPath, 1)) || 1;
    element.style.width = `${Math.max(0, Math.min(100, value / max * 100))}%`;
  });
  updateDisplays();
}

function displayText(item) {
  let raw = item.text || "";
  if (item.template) raw = interpolate(item.template);
  else if (item.path) raw = getPath(app.state, item.path, "");
  return String(item.labels?.[String(raw)] ?? raw);
}

function updateDisplays() {
  for (const [partId, spec] of Object.entries(app.config?.displays || {})) {
    if (spec.kind !== "ssd1306") continue;
    const element = app.partElements.get(partId)?.element;
    if (!element || !(element.imageData instanceof ImageData)) continue;
    const width = Number(spec.width || element.screenWidth || 128);
    const height = Number(spec.height || element.screenHeight || 64);
    const bitmap = document.createElement("canvas");
    bitmap.width = width;
    bitmap.height = height;
    const display = bitmap.getContext("2d");
    display.fillStyle = spec.background || "#000000";
    display.fillRect(0, 0, width, height);
    display.fillStyle = spec.foreground || "#c8f7ff";
    display.strokeStyle = spec.foreground || "#c8f7ff";

    for (const item of spec.items || []) {
      display.save();
      display.globalAlpha = Number(item.opacity ?? 1);
      display.fillStyle = item.color || spec.foreground || "#c8f7ff";
      display.strokeStyle = item.color || spec.foreground || "#c8f7ff";
      if (item.kind === "line") {
        display.lineWidth = Number(item.lineWidth || 1);
        display.beginPath();
        display.moveTo(Number(item.x || 0), Number(item.y || 0));
        display.lineTo(Number(item.x2 ?? width), Number(item.y2 ?? item.y ?? 0));
        display.stroke();
      } else if (item.kind === "progress") {
        const value = Number(getPath(app.state, item.path, 0));
        const max = Number(getPath(app.state, item.maxPath, 1)) || 1;
        const itemWidth = Number(item.width || width);
        const itemHeight = Number(item.height || 2);
        display.globalAlpha = Number(item.trackOpacity ?? 0.25);
        display.fillRect(Number(item.x || 0), Number(item.y || 0), itemWidth, itemHeight);
        display.globalAlpha = Number(item.opacity ?? 1);
        display.fillRect(
          Number(item.x || 0),
          Number(item.y || 0),
          itemWidth * Math.max(0, Math.min(1, value / max)),
          itemHeight,
        );
      } else {
        display.font = item.font || "8px ui-monospace, monospace";
        display.textAlign = item.align || "left";
        display.textBaseline = item.baseline || "top";
        display.fillText(displayText(item), Number(item.x || 0), Number(item.y || 0));
      }
      display.restore();
    }
    element.imageData = display.getImageData(0, 0, width, height);
    element.redraw?.();
  }
}

function stateElement(spec, className = "") {
  const element = document.createElement(spec.tag || "span");
  element.className = className || spec.className || "";
  if (spec.label) {
    const label = document.createElement("span");
    label.textContent = spec.label;
    element.appendChild(label);
    const value = document.createElement("b");
    value.dataset.statePath = spec.path;
    if (spec.template) value.dataset.template = spec.template;
    if (spec.labels) value.dataset.labels = JSON.stringify(spec.labels);
    element.appendChild(value);
  } else {
    if (spec.path || spec.template) element.dataset.statePath = spec.path || "";
    if (spec.template) element.dataset.template = spec.template;
    if (spec.labels) element.dataset.labels = JSON.stringify(spec.labels);
  }
  return element;
}

function buildInterface() {
  document.title = app.config.name || "CircuitLab";
  document.getElementById("brandName").textContent = app.config.name || "Circuit Lab";
  document.getElementById("brandSubtitle").textContent = app.config.subtitle || "Offline wiring simulator";
  document.getElementById("brandMark").textContent = app.config.mark || "CL";
  document.getElementById("statePanelTitle").textContent = app.config.ui?.statePanel?.title || "State";

  const statusStrip = document.getElementById("statusStrip");
  statusStrip.replaceChildren();
  for (const spec of app.config.ui?.statusStrip || []) {
    if (spec.kind === "badge") {
      const element = document.createElement("span");
      element.dataset.badgePath = spec.path;
      element.dataset.labels = JSON.stringify(spec.labels || {});
      element.dataset.tones = JSON.stringify(spec.tones || {});
      element.dataset.baseClass = spec.className || "badge";
      statusStrip.appendChild(element);
    } else {
      statusStrip.appendChild(stateElement(spec, spec.className || "status-item"));
    }
  }

  const panel = app.config.ui?.statePanel || {};
  const badge = document.getElementById("statePanelBadge");
  if (panel.badge) {
    badge.dataset.badgePath = panel.badge.path;
    badge.dataset.labels = JSON.stringify(panel.badge.labels || {});
    badge.dataset.tones = JSON.stringify(panel.badge.tones || {});
    badge.dataset.baseClass = panel.badge.className || "mode-label";
  } else badge.hidden = true;
  const bitGrid = document.getElementById("bitGrid");
  bitGrid.replaceChildren(...(panel.fields || []).map(spec => stateElement(spec)));
  const progress = document.getElementById("bufferTrack");
  if (panel.progress) {
    progress.dataset.progressPath = panel.progress.path;
    progress.dataset.progressMaxPath = panel.progress.maxPath;
  } else progress.parentElement.hidden = true;
  const meta = document.getElementById("bufferMeta");
  meta.replaceChildren(...(panel.meta || []).map(spec => stateElement(spec)));

  const wiringList = document.getElementById("wiringList");
  wiringList.replaceChildren();
  for (const row of app.config.wiring?.rows || []) {
    const element = document.createElement("button");
    element.type = "button";
    element.className = row.className || "";
    element.dataset.wireId = row.wireId;
    element.innerHTML = `<i></i><b>${row.label}</b><span>${row.pin}</span>`;
    element.style.setProperty("--net-color", colors[row.color] || row.color || colors.black);
    element.addEventListener("click", () => {
      const wire = app.wirePaths.find(candidate => candidate.id === row.wireId);
      if (wire) selectWire(wire);
    });
    element.addEventListener("mouseenter", () => { app.hoveredWire = row.wireId; draw(); });
    element.addEventListener("mouseleave", () => {
      if (app.hoveredWire === row.wireId) app.hoveredWire = null;
      draw();
    });
    wiringList.appendChild(element);
  }
  keyboardBindings.clear();
  for (const [code, partId] of Object.entries(app.config.keyboard || {})) keyboardBindings.set(code, partId);
}

async function loadBoardGeometries() {
  app.boardGeometries.clear();
  await Promise.all(Object.entries(app.config.boards || {}).map(async ([type, board]) => {
    const geometry = await api(board.geometry);
    const pinEntries = Array.isArray(geometry.pins)
      ? geometry.pins.map(pin => [pin.name, [pin.x, pin.y]])
      : Object.entries(geometry.pins || {}).map(([name, pin]) => [name, [pin.x, pin.y]]);
    const pins = Object.fromEntries(pinEntries.filter(([, point]) => point.every(Number.isFinite)));
    app.boardGeometries.set(type, { width: geometry.width, height: geometry.height, pins });
  }));
}

function appendEvents(events) {
  for (const event of events) {
    if (event.id <= app.clearedBefore) continue;
    const fields = Object.entries(event)
      .filter(([key]) => !["id", "time_ms", "name"].includes(key))
      .map(([key, value]) => `${key}=${value}`)
      .join(" ");
    const line = document.createElement("div");
    line.className = "log-line";
    line.innerHTML = `<span class="log-time">${String(event.time_ms).padStart(6, "0")}</span><span class="log-name ${event.name.toLowerCase()}">${event.name}</span><span class="log-fields"></span>`;
    line.querySelector(".log-fields").textContent = fields;
    serialLog.appendChild(line);
    app.cursor = Math.max(app.cursor, event.id);
  }
  while (serialLog.children.length > 300) serialLog.firstElementChild.remove();
  if (events.length) serialLog.scrollTop = serialLog.scrollHeight;
}

async function poll() {
  try {
    const state = await api(`/api/state?since=${app.cursor}`);
    app.state = state;
    appendEvents(state.events || []);
    updateStatus();
    draw();
  } catch (error) {
    if (!app.unloading) console.error(error);
  } finally {
    window.setTimeout(poll, 120);
  }
}

document.getElementById("fitButton").addEventListener("click", fitCircuit);
document.getElementById("autoRouteButton").addEventListener("click", () => autoRoute());
document.getElementById("resetButton").addEventListener("click", () => sendInput(app.config.resetInput || { type: "reset" }));
document.getElementById("rotateLeftButton").addEventListener("click", () => rotateSelected(-90));
document.getElementById("rotateRightButton").addEventListener("click", () => rotateSelected(90));
document.querySelectorAll("[data-interaction-mode]").forEach((button) => {
  button.addEventListener("click", () => setInteractionMode(button.dataset.interactionMode));
});
document.getElementById("layoutResetButton").addEventListener("click", async () => {
  await api("/api/layout", { method: "DELETE" });
  app.diagram = await api("/api/diagram");
  applySavedRoutes();
  clearSelection();
  createPartElements();
  fitCircuit();
  scheduleDefaultRouting();
});
document.getElementById("clearButton").addEventListener("click", () => {
  serialLog.replaceChildren();
  app.clearedBefore = app.cursor;
});
window.addEventListener("resize", resizeCanvas);
window.addEventListener("beforeunload", () => { app.unloading = true; });
new ResizeObserver(() => window.requestAnimationFrame(resizeCanvas))
  .observe(document.querySelector(".stage"));

async function start() {
  app.config = await api("/api/lab-config");
  await loadBoardGeometries();
  buildInterface();
  app.diagram = await api("/api/diagram");
  applySavedRoutes();
  app.state = await api("/api/state?since=0");
  createPartElements();
  appendEvents(app.state.events || []);
  updateStatus();
  resizeCanvas(true);
  scheduleDefaultRouting();
  poll();
}

window.__runeCircuitDebug = {
  get mode() { return app.interactionMode; },
  get selectedWireId() { return app.selectedWireId; },
  get layout() { return layoutPayload(); },
  pinPoint,
  connections() {
    return app.diagram.connections.map((connection) => ({
      connection,
      start: pinPoint(connection[0]),
      end: pinPoint(connection[1]),
    }));
  },
  routes() {
    return app.wirePaths.map(({ id, type, route, hitPoint }) => ({ id, type, route, hitPoint }));
  },
  hitTest(x, y) {
    const bounds = canvas.getBoundingClientRect();
    const event = { clientX: bounds.left + x, clientY: bounds.top + y };
    return { part: hitPart(event)?.id || null, wire: hitWire(event)?.id || null };
  },
  autoRoute,
  validateWiring,
};
window.__circuitLabDebug = window.__runeCircuitDebug;

start().catch((error) => {
  serialLog.textContent = `Startup failed: ${error.message}`;
});
