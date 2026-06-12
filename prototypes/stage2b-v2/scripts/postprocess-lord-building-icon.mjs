import fs from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import { execFile } from "node:child_process";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";
import { trimTransparentPng } from "./lib/image-providers.mjs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const execFileAsync = promisify(execFile);
const projectRoot = path.resolve(__dirname, "..");
const outputDir = path.join(projectRoot, "src", "assets", "generated", "lords-home", "buildings");
const manifestPath = path.join(outputDir, "manifest-local-imagegen.json");
const defaultHelperPath = path.join(
  os.homedir(),
  ".codex",
  "skills",
  ".system",
  "imagegen",
  "scripts",
  "remove_chroma_key.py",
);

const outputFiles = {
  b_training_yard: "building-training-yard-v1.png",
  b_barracks: "building-barracks-v1.png",
  b_archery_range: "building-archery-range-v1.png",
  b_stables: "building-stables-v1.png",
  b_siege_yard: "building-siege-yard-v1.png",
  b_war_academy: "building-war-academy-v1.png",
  b_market: "building-market-v1.png",
  b_tax_office: "building-tax-office-v1.png",
  b_storehouse: "building-storehouse-v1.png",
  b_bank: "building-bank-v1.png",
  b_treasury_hall: "building-treasury-hall-v1.png",
  b_notice_board: "building-notice-board-v1.png",
  b_envoy_hall: "building-envoy-hall-v1.png",
  b_map_room: "building-map-room-v1.png",
  b_raid_office: "building-raid-office-v1.png",
  b_war_council: "building-war-council-v1.png",
  b_mage_study: "building-mage-study-v1.png",
  b_alchemy_lab: "building-alchemy-lab-v1.png",
  b_scrying_room: "building-scrying-room-v1.png",
  b_wards: "building-wards-v1.png",
  b_ritual_chamber: "building-ritual-chamber-v1.png",
};

const id = readArg("--id");
const sourcePath = readArg("--source");
const pythonExe = readArg("--python") || process.env.PYTHON || "python";
const helperPath = readArg("--helper") || defaultHelperPath;

if (!id || !outputFiles[id]) {
  throw new Error(`Unknown or missing --id. Known ids: ${Object.keys(outputFiles).join(", ")}`);
}

if (!sourcePath) {
  throw new Error("Missing --source=<generated image path>");
}

await fs.mkdir(outputDir, { recursive: true });

const outputPath = path.join(outputDir, outputFiles[id]);
const alphaPath = `${outputPath}.alpha.png`;

await execFileAsync(pythonExe, [
  helperPath,
  "--input",
  sourcePath,
  "--out",
  alphaPath,
  "--auto-key",
  "border",
  "--soft-matte",
  "--transparent-threshold",
  "28",
  "--opaque-threshold",
  "180",
  "--despill",
  "--force",
]);
await trimTransparentPng(alphaPath, outputPath, 0.14);
await fs.unlink(alphaPath).catch(() => {});

const manifest = await readManifest();
manifest.generated_at = new Date().toISOString();
manifest.provider = "codex-imagegen";
manifest.assets = manifest.assets.filter((asset) => asset.id !== id);
manifest.assets.push({
  id,
  file: outputFiles[id],
  source: sourcePath,
});
manifest.assets.sort((a, b) => a.id.localeCompare(b.id));

await fs.writeFile(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`, "utf8");

console.log(`icon: ${path.relative(projectRoot, outputPath)}`);

function readArg(name) {
  const prefix = `${name}=`;
  const value = process.argv.find((arg) => arg.startsWith(prefix));
  return value ? value.slice(prefix.length) : "";
}

async function readManifest() {
  try {
    const content = await fs.readFile(manifestPath, "utf8");
    return JSON.parse(content);
  } catch {
    return { generated_at: "", provider: "codex-imagegen", assets: [] };
  }
}
