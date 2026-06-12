import fs from "node:fs";
import path from "node:path";
import { PNG } from "pngjs";

const sourcePath = path.resolve("src/assets/generated/lord-map-v2.png");
const outDir = path.resolve("src/assets/generated/map-cutouts");

const source = PNG.sync.read(fs.readFileSync(sourcePath));
fs.mkdirSync(outDir, { recursive: true });

const measuredViewport = { width: 839, height: 1005 };
const scale = Math.max(measuredViewport.width / source.width, measuredViewport.height / source.height);
const cropX = (source.width * scale - measuredViewport.width) / 2;
const cropY = (source.height * scale - measuredViewport.height) / 2;

const locations = [
  { id: "north-fort", x: 22, y: 28, w: 250, h: 180 },
  { id: "witchwood", x: 34, y: 45, w: 250, h: 190 },
  { id: "river-gate", x: 47, y: 38, w: 280, h: 160 },
  { id: "capital", x: 51, y: 55, w: 430, h: 310 },
  { id: "fields", x: 67, y: 58, w: 280, h: 190 },
  { id: "swamp", x: 78, y: 72, w: 300, h: 220 },
  { id: "ruins", x: 17, y: 72, w: 300, h: 220 },
  { id: "ember-fort", x: 56, y: 80, w: 250, h: 180 },
  { id: "arcane", x: 73, y: 31, w: 270, h: 190 }
];

const clamp = (value, min, max) => Math.max(min, Math.min(max, value));
const smooth = (edge0, edge1, x) => {
  const t = clamp((x - edge0) / (edge1 - edge0), 0, 1);
  return t * t * (3 - 2 * t);
};

const manifest = [];

for (const location of locations) {
  const centerX = (location.x / 100 * measuredViewport.width + cropX) / scale;
  const centerY = (location.y / 100 * measuredViewport.height + cropY) / scale;
  const startX = Math.round(clamp(centerX - location.w / 2, 0, source.width - location.w));
  const startY = Math.round(clamp(centerY - location.h / 2, 0, source.height - location.h));
  const out = new PNG({ width: location.w, height: location.h });

  for (let y = 0; y < location.h; y += 1) {
    for (let x = 0; x < location.w; x += 1) {
      const sourceIndex = ((startY + y) * source.width + startX + x) * 4;
      const outIndex = (y * location.w + x) * 4;
      const dx = (x + 0.5 - location.w / 2) / (location.w / 2);
      const dy = (y + 0.5 - location.h / 2) / (location.h / 2);
      const distance = Math.sqrt(dx * dx + dy * dy);
      const feather = 1 - smooth(0.72, 1, distance);
      const alpha = Math.round(source.data[sourceIndex + 3] * feather);

      out.data[outIndex] = alpha ? source.data[sourceIndex] : 0;
      out.data[outIndex + 1] = alpha ? source.data[sourceIndex + 1] : 0;
      out.data[outIndex + 2] = alpha ? source.data[sourceIndex + 2] : 0;
      out.data[outIndex + 3] = alpha;
    }
  }

  const fileName = `${location.id}.png`;
  fs.writeFileSync(path.join(outDir, fileName), PNG.sync.write(out));
  manifest.push({
    id: location.id,
    file: fileName,
    source: { x: Math.round(centerX), y: Math.round(centerY), width: location.w, height: location.h },
    screen: { x: location.x, y: location.y },
    displayWidthPercent: Number(((location.w * scale) / measuredViewport.width * 100).toFixed(2))
  });
}

fs.writeFileSync(path.join(outDir, "manifest.json"), `${JSON.stringify(manifest, null, 2)}\n`);
console.log(`created ${manifest.length} map cutouts in ${outDir}`);
