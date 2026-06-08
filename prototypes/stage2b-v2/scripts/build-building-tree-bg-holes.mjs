import fs from "node:fs";
import path from "node:path";
import { PNG } from "pngjs";

const root = path.resolve(import.meta.dirname, "..");
const sourcePath = path.join(root, "src", "assets", "generated", "building-tree-bg-v2.png");
const targetPath = path.join(root, "src", "assets", "generated", "building-tree-bg-v6-holes.png");
const previewPath = path.join(root, "src", "assets", "generated", "building-tree-bg-v6-holes-preview.png");

const nodes = [
  { id: "b_training_yard", branch: "military", x: 53.0, y: 67.4, prereq: [] },
  { id: "b_barracks", branch: "military", x: 56.0, y: 56.4, prereq: ["b_training_yard"] },
  { id: "b_archery_range", branch: "military", x: 50.2, y: 56.4, prereq: ["b_training_yard"] },
  { id: "b_stables", branch: "military", x: 56.0, y: 44.8, prereq: ["b_barracks"] },
  { id: "b_siege_yard", branch: "military", x: 50.2, y: 44.8, prereq: ["b_archery_range"] },
  { id: "b_war_academy", branch: "military", x: 50.2, y: 13.2, prereq: ["b_siege_yard", "b_war_council"] },
  { id: "b_market", branch: "economy", x: 28.6, y: 67.4, prereq: [] },
  { id: "b_tax_office", branch: "economy", x: 25.4, y: 56.4, prereq: ["b_market"] },
  { id: "b_storehouse", branch: "economy", x: 32.0, y: 56.4, prereq: ["b_market"] },
  { id: "b_bank", branch: "economy", x: 32.0, y: 44.8, prereq: ["b_tax_office", "b_storehouse"] },
  { id: "b_treasury_hall", branch: "economy", x: 32.0, y: 30.0, prereq: ["b_bank"] },
  { id: "b_notice_board", branch: "order", x: 66.4, y: 67.4, prereq: [] },
  { id: "b_envoy_hall", branch: "order", x: 69.5, y: 56.4, prereq: ["b_notice_board"] },
  { id: "b_map_room", branch: "order", x: 63.8, y: 56.4, prereq: ["b_notice_board"] },
  { id: "b_raid_office", branch: "order", x: 63.8, y: 44.8, prereq: ["b_map_room", "b_stables"] },
  { id: "b_war_council", branch: "order", x: 63.8, y: 30.0, prereq: ["b_raid_office", "b_envoy_hall"] },
  { id: "b_mage_study", branch: "magic", x: 40.6, y: 67.4, prereq: [] },
  { id: "b_alchemy_lab", branch: "magic", x: 37.5, y: 56.4, prereq: ["b_mage_study"] },
  { id: "b_scrying_room", branch: "magic", x: 43.8, y: 56.4, prereq: ["b_mage_study"] },
  { id: "b_wards", branch: "magic", x: 43.8, y: 44.8, prereq: ["b_scrying_room", "b_alchemy_lab"] },
  { id: "b_ritual_chamber", branch: "magic", x: 40.6, y: 13.2, prereq: ["b_wards", "b_treasury_hall"] }
];

const branchColors = {
  military: [212, 111, 94, 255],
  economy: [222, 179, 86, 255],
  order: [119, 202, 142, 255],
  magic: [174, 145, 236, 255]
};

const builtIds = new Set([
  "b_training_yard",
  "b_market",
  "b_notice_board",
  "b_mage_study",
  "b_barracks",
  "b_tax_office",
  "b_envoy_hall"
]);

const image = PNG.sync.read(fs.readFileSync(sourcePath));
const out = new PNG({ width: image.width, height: image.height });
image.data.copy(out.data);

const byId = new Map(nodes.map((node) => [node.id, node]));
const slotWidth = Math.round(image.width * 0.052);
const slotHeight = Math.round(image.height * 0.049);
const graphRect = {
  x: Math.round(image.width * 0.205),
  y: Math.round(image.height * 0.09),
  w: Math.round(image.width * 0.528),
  h: Math.round(image.height * 0.635)
};
const bottomHudTop = Math.round(image.height * 0.745);

function index(x, y) {
  return (y * out.width + x) * 4;
}

function getPixel(x, y) {
  const clampedX = Math.max(0, Math.min(out.width - 1, Math.round(x)));
  const clampedY = Math.max(0, Math.min(out.height - 1, Math.round(y)));
  const i = index(clampedX, clampedY);
  return [out.data[i], out.data[i + 1], out.data[i + 2], out.data[i + 3]];
}

function setPixel(x, y, color) {
  if (x < 0 || y < 0 || x >= out.width || y >= out.height) return;
  const i = index(Math.round(x), Math.round(y));
  out.data[i] = color[0];
  out.data[i + 1] = color[1];
  out.data[i + 2] = color[2];
  out.data[i + 3] = color[3];
}

function blendPixel(x, y, color) {
  if (x < 0 || y < 0 || x >= out.width || y >= out.height) return;
  const i = index(Math.round(x), Math.round(y));
  const alpha = color[3] / 255;
  const inv = 1 - alpha;
  out.data[i] = Math.round(color[0] * alpha + out.data[i] * inv);
  out.data[i + 1] = Math.round(color[1] * alpha + out.data[i + 1] * inv);
  out.data[i + 2] = Math.round(color[2] * alpha + out.data[i + 2] * inv);
  out.data[i + 3] = Math.round(255 * alpha + out.data[i + 3] * inv);
}

function fillRect(x, y, w, h, color, mode = "blend") {
  for (let yy = Math.max(0, y); yy < Math.min(out.height, y + h); yy += 1) {
    for (let xx = Math.max(0, x); xx < Math.min(out.width, x + w); xx += 1) {
      if (mode === "set") setPixel(xx, yy, color);
      else blendPixel(xx, yy, color);
    }
  }
}

function pointInPolygon(x, y, polygon) {
  let inside = false;
  for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
    const xi = polygon[i][0];
    const yi = polygon[i][1];
    const xj = polygon[j][0];
    const yj = polygon[j][1];
    const intersects = yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi;
    if (intersects) inside = !inside;
  }
  return inside;
}

function fillPolygon(polygon, color, mode = "blend") {
  const minX = Math.floor(Math.min(...polygon.map((point) => point[0])));
  const maxX = Math.ceil(Math.max(...polygon.map((point) => point[0])));
  const minY = Math.floor(Math.min(...polygon.map((point) => point[1])));
  const maxY = Math.ceil(Math.max(...polygon.map((point) => point[1])));
  for (let y = minY; y <= maxY; y += 1) {
    for (let x = minX; x <= maxX; x += 1) {
      if (pointInPolygon(x + 0.5, y + 0.5, polygon)) {
        if (mode === "set") setPixel(x, y, color);
        else blendPixel(x, y, color);
      }
    }
  }
}

function strokeLine(x1, y1, x2, y2, color, width = 2) {
  const dx = x2 - x1;
  const dy = y2 - y1;
  const steps = Math.max(Math.abs(dx), Math.abs(dy), 1);
  for (let step = 0; step <= steps; step += 1) {
    const t = step / steps;
    const x = x1 + dx * t;
    const y = y1 + dy * t;
    const radius = width / 2;
    for (let yy = Math.floor(y - radius); yy <= Math.ceil(y + radius); yy += 1) {
      for (let xx = Math.floor(x - radius); xx <= Math.ceil(x + radius); xx += 1) {
        const dist = Math.hypot(xx - x, yy - y);
        if (dist <= radius) blendPixel(xx, yy, color);
      }
    }
  }
}

function strokePath(points, color, width) {
  for (let i = 0; i < points.length - 1; i += 1) {
    strokeLine(points[i][0], points[i][1], points[i + 1][0], points[i + 1][1], color, width);
  }
}

function strokePolygon(polygon, color, width) {
  for (let i = 0; i < polygon.length; i += 1) {
    const a = polygon[i];
    const b = polygon[(i + 1) % polygon.length];
    strokeLine(a[0], a[1], b[0], b[1], color, width);
  }
}

function octagon(cx, cy, w, h, cut = 12) {
  const x0 = cx - w / 2;
  const x1 = cx + w / 2;
  const y0 = cy - h / 2;
  const y1 = cy + h / 2;
  return [
    [x0 + cut, y0],
    [x1 - cut, y0],
    [x1, y0 + cut],
    [x1, y1 - cut],
    [x1 - cut, y1],
    [x0 + cut, y1],
    [x0, y1 - cut],
    [x0, y0 + cut]
  ];
}

function transparentPolygon(polygon) {
  fillPolygon(polygon, [0, 0, 0, 0], "set");
}

function position(node) {
  return {
    x: Math.round((node.x / 100) * out.width),
    y: Math.round((node.y / 100) * out.height)
  };
}

// Remove the baked bottom inventory strip so the live home HUD can show through.
fillRect(0, bottomHudTop, out.width, out.height - bottomHudTop, [0, 0, 0, 0], "set");

// Rebuild the central graph board with a dark scratched surface over the stale generated graph.
fillRect(graphRect.x, graphRect.y, graphRect.w, graphRect.h, [5, 16, 22, 238], "blend");
for (let y = graphRect.y; y < graphRect.y + graphRect.h; y += 1) {
  for (let x = graphRect.x; x < graphRect.x + graphRect.w; x += 1) {
    const noise = ((x * 17 + y * 31 + (x ^ y)) % 37) - 18;
    const i = index(x, y);
    out.data[i] = Math.max(0, Math.min(255, out.data[i] + noise * 0.22));
    out.data[i + 1] = Math.max(0, Math.min(255, out.data[i + 1] + noise * 0.25));
    out.data[i + 2] = Math.max(0, Math.min(255, out.data[i + 2] + noise * 0.32));
  }
}

for (let x = graphRect.x; x <= graphRect.x + graphRect.w; x += Math.round(out.width * 0.051)) {
  strokeLine(x, graphRect.y, x, graphRect.y + graphRect.h, [130, 165, 168, 28], 1);
}
for (let y = graphRect.y; y <= graphRect.y + graphRect.h; y += Math.round(out.height * 0.105)) {
  strokeLine(graphRect.x, y, graphRect.x + graphRect.w, y, [130, 165, 168, 18], 1);
}

strokePolygon(
  [
    [graphRect.x, graphRect.y],
    [graphRect.x + graphRect.w, graphRect.y],
    [graphRect.x + graphRect.w, graphRect.y + graphRect.h],
    [graphRect.x, graphRect.y + graphRect.h]
  ],
  [174, 132, 72, 95],
  2
);

// Draw the actual dependency graph from the building tree.
for (const node of nodes) {
  const to = position(node);
  for (const prereqId of node.prereq) {
    const prereq = byId.get(prereqId);
    if (!prereq) continue;
    const from = position(prereq);
    const sameRow = Math.abs(from.y - to.y) < slotHeight * 0.8;
    const halo = [18, 26, 28, 116];
    const line = [122, 132, 124, 62];
    let pathPoints;
    if (prereq.id === "b_stables" && node.id === "b_raid_office") {
      pathPoints = [
        [from.x + slotWidth / 2 - 4, from.y],
        [to.x - slotWidth / 2 + 4, to.y]
      ];
    } else if (prereq.id === "b_envoy_hall" && node.id === "b_war_council") {
      const start = [from.x, from.y - slotHeight / 2 + 4];
      const end = [to.x + slotWidth / 2 - 4, to.y];
      pathPoints = [start, [start[0], end[1]], end];
    } else if (sameRow) {
      const direction = to.x >= from.x ? 1 : -1;
      const start = [from.x + direction * (slotWidth / 2 - 4), from.y - slotHeight * 0.12];
      const end = [to.x - direction * (slotWidth / 2 - 4), to.y - slotHeight * 0.12];
      const routeY = Math.round(Math.min(from.y, to.y) - slotHeight * 0.95);
      pathPoints = [start, [start[0], routeY], [end[0], routeY], end];
    } else {
      const start = [from.x, from.y - slotHeight / 2 + 4];
      const end = [to.x, to.y + slotHeight / 2 - 4];
      const midY = Math.round((start[1] + end[1]) / 2);
      pathPoints = [start, [start[0], midY], [end[0], midY], end];
    }
    strokePath(pathPoints, halo, 5);
    strokePath(pathPoints, line, 2);
  }
}

// Cut transparent icon apertures and draw ornate metal frames around them.
for (const node of nodes) {
  const p = position(node);
  const tone = branchColors[node.branch];
  const active = builtIds.has(node.id);
  const outer = octagon(p.x, p.y, slotWidth, slotHeight, Math.round(slotHeight * 0.28));
  const inner = octagon(p.x, p.y, Math.round(slotWidth * 0.63), Math.round(slotHeight * 0.72), Math.round(slotHeight * 0.18));
  const shadow = octagon(p.x + 2, p.y + 3, slotWidth, slotHeight, Math.round(slotHeight * 0.28));
  fillPolygon(shadow, [0, 0, 0, 86], "blend");
  fillPolygon(outer, [7, 18, 24, active ? 205 : 165], "blend");
  transparentPolygon(inner);
  strokePolygon(outer, [27, 22, 16, 190], 5);
  strokePolygon(outer, [188, 136, 72, active ? 170 : 112], 3);
  strokePolygon(outer, [tone[0], tone[1], tone[2], active ? 115 : 70], 1);
  strokePolygon(inner, [234, 195, 111, active ? 95 : 58], 1);
}

// A preview with a muted underlay in the transparent apertures is useful for asset QA.
const preview = new PNG({ width: out.width, height: out.height });
out.data.copy(preview.data);
for (const node of nodes) {
  const p = position(node);
  const inner = octagon(p.x, p.y, Math.round(slotWidth * 0.63), Math.round(slotHeight * 0.72), Math.round(slotHeight * 0.18));
  const tone = branchColors[node.branch];
  fillPolygon(inner, [tone[0], tone[1], tone[2], 60], "blend");
}

fs.writeFileSync(targetPath, PNG.sync.write(out));
fs.writeFileSync(previewPath, PNG.sync.write(preview));

let transparent = 0;
for (let i = 3; i < out.data.length; i += 4) {
  if (out.data[i] === 0) transparent += 1;
}

console.log(`wrote ${targetPath}`);
console.log(`wrote ${previewPath}`);
console.log(`transparent pixels: ${transparent}`);
