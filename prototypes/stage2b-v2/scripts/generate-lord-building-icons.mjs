import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { loadExternalEnv } from "./lib/env.mjs";
import {
  generateOpenRouterImage,
  removeChromaKeyPng,
  trimTransparentPng,
} from "./lib/image-providers.mjs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.resolve(__dirname, "..");
const outputDir = path.join(projectRoot, "src", "assets", "generated", "lords-home", "buildings");
const rawDir = path.join(outputDir, "raw");
const manifestPath = path.join(outputDir, "manifest.json");

const MODEL = process.env.OPENROUTER_IMAGE_MODEL || "openai/gpt-5.4-image-2";
const KEY_COLOR = "#00ff00";

const STYLE_BRIEF = [
  "original dark Slavic fantasy strategy game building icon",
  "small 3D painted miniature, front-facing with a slight isometric tilt",
  "aged stone, dark timber, forged iron, old brass, cold moonlit teal shadows",
  "readable as a building/object at 64 pixels",
  "strong silhouette, centered composition, generous padding",
  "polished PC game UI asset, not a web icon, not vector line art",
].join(", ");

const KEY_INSTRUCTIONS = [
  `Place the subject on a perfectly flat solid ${KEY_COLOR} chroma-key background for removal.`,
  "The background must be one uniform color with no gradients, texture, floor plane, shadow, glow, vignette, or reflection.",
  `Do not use ${KEY_COLOR}, bright green, neon green, or green screen spill anywhere inside the subject.`,
  "No cast shadow, no contact shadow, no frame, no circular badge, no text, no numbers, no watermark.",
].join(" ");

const NEGATIVE = [
  "official Witcher art",
  "official Warcraft art",
  "official Heroes of Might and Magic art",
  "copied trademarked logo",
  "readable text",
  "Cyrillic letters",
  "English letters",
  "flat vector icon",
  "line icon",
  "website UI",
  "modern city building",
  "humans or portraits",
  "green screen inside the object",
  "background scenery",
  "frame",
  "card",
  "watermark",
].join(", ");

const jobs = [
  {
    id: "b_training_yard",
    file: "building-training-yard-v1.png",
    name: "Training Yard",
    subject: "a compact wooden training yard: straw practice dummies, weapon racks, low palisade posts, trampled dirt, red-brown military accents",
  },
  {
    id: "b_barracks",
    file: "building-barracks-v1.png",
    name: "Barracks",
    subject: "a fortified barracks hall: dark timber and stone, shields by the door, red-brown banners without symbols, heavy roof beams",
  },
  {
    id: "b_archery_range",
    file: "building-archery-range-v1.png",
    name: "Archery Range",
    subject: "an archery range pavilion: bow rack, two round practice targets, short fence, leather and red-brown military accents",
  },
  {
    id: "b_stables",
    file: "building-stables-v1.png",
    name: "Stables",
    subject: "a medieval stable: arched dark doors, hay bundles, tack hooks, horseshoe ornament without text, warm wood and red-brown accents",
  },
  {
    id: "b_siege_yard",
    file: "building-siege-yard-v1.png",
    name: "Siege Yard",
    subject: "a siege workshop yard: small ballista frame, timber crane, iron bolts, stacked beams, compact red-brown military construction",
  },
  {
    id: "b_war_academy",
    file: "building-war-academy-v1.png",
    name: "War Academy",
    subject: "a stern stone war academy keep: arched gate, training standards without symbols, crenellations, disciplined red-brown military accents",
  },
  {
    id: "b_market",
    file: "building-market-v1.png",
    name: "Market",
    subject: "a compact medieval market stall icon, not a long building: one bright central awning, coin scales, a few crates and barrels, warm lantern light, readable worn-gold trade accents, chunky clear silhouette for a tiny game tech-tree slot",
  },
  {
    id: "b_tax_office",
    file: "building-tax-office-v1.png",
    name: "Tax Office",
    subject: "a compact medieval tax office icon, not a long building: small counting house facade, ledger desk visible through an arch, coin chest, sealed scrolls without text, bright old-brass tax seal, chunky clear silhouette for a tiny game tech-tree slot",
  },
  {
    id: "b_storehouse",
    file: "building-storehouse-v1.png",
    name: "Storehouse",
    subject: "a compact storehouse icon, not a long warehouse: sturdy heavy double doors, stacked crates and barrels in front, rope and small pulley, warm lantern highlights, old brass storage accents, chunky clear silhouette for a tiny game tech-tree slot",
  },
  {
    id: "b_bank",
    file: "building-bank-v1.png",
    name: "Bank",
    subject: "a compact fortified medieval bank icon, not a long building: small vault door, two short stone pillars, coin coffer, old brass lockwork, worn gold highlights, chunky clear silhouette for a tiny game tech-tree slot",
  },
  {
    id: "b_treasury_hall",
    file: "building-treasury-hall-v1.png",
    name: "Treasury Hall",
    subject: "a grand treasury hall miniature: heavy coffer, two short stone columns, guarded vault arch, warm gold metal highlights",
  },
  {
    id: "b_notice_board",
    file: "building-notice-board-v1.png",
    name: "Notice Board",
    subject: "a wooden notice board structure: pinned parchment sheets with no readable text, wax seals, small roof, muted brass and parchment accents",
  },
  {
    id: "b_envoy_hall",
    file: "building-envoy-hall-v1.png",
    name: "Envoy Hall",
    subject: "a diplomatic hall: crossed blank banners, sealed scrolls, arched doorway, polished dark wood and parchment accents, no symbols",
  },
  {
    id: "b_map_room",
    file: "building-map-room-v1.png",
    name: "Map Room",
    subject: "a cartography room: round map table, compass, rolled maps with no readable markings, lantern, parchment and brass accents",
  },
  {
    id: "b_raid_office",
    file: "building-raid-office-v1.png",
    name: "Raid Office",
    subject: "a raid command office: small war table, blank route map, dagger markers, dark tent-and-timber structure, parchment and brass accents",
  },
  {
    id: "b_war_council",
    file: "building-war-council-v1.png",
    name: "War Council",
    subject: "a strategic council chamber: round command table, miniature banners with no symbols, candles, dark wood, parchment and brass accents",
  },
  {
    id: "b_mage_study",
    file: "building-mage-study-v1.png",
    name: "Mage Study",
    subject: "a mage study tower room: stacked books, crystal focus, small arched tower, cold violet arcane highlights, no runic text",
  },
  {
    id: "b_alchemy_lab",
    file: "building-alchemy-lab-v1.png",
    name: "Alchemy Lab",
    subject: "an alchemy laboratory: glass flasks, alembic, small cauldron, stone bench, cold violet and amber magical highlights, no labels",
  },
  {
    id: "b_scrying_room",
    file: "building-scrying-room-v1.png",
    name: "Scrying Room",
    subject: "a scrying chamber: crystal orb, dark mirror, crescent stand, candle circle, cold violet magical glow, no written symbols",
  },
  {
    id: "b_wards",
    file: "building-wards-v1.png",
    name: "Wards",
    subject: "a warding shrine: short stone obelisks, protective metal rings, glowing violet barrier facets, old candles, no readable runes",
  },
  {
    id: "b_ritual_chamber",
    file: "building-ritual-chamber-v1.png",
    name: "Ritual Chamber",
    subject: "a ritual chamber: low stone altar, candle circle, suspended crystal, dark carved slab, deep violet arcane highlights, no readable symbols",
  },
];

function buildPrompt(job) {
  return [
    `Create one isolated building icon for a lord castle tech tree slot: ${job.name}.`,
    `Subject: ${job.subject}.`,
    STYLE_BRIEF,
    KEY_INSTRUCTIONS,
    "Composition: the entire subject must fit inside the canvas with transparent-ready empty padding around it; keep the visual center stable so it can be placed exactly under a fixed UI slot.",
    "Rendering: painterly realism with crisp edges and material depth, dark fantasy but readable in a tiny octagonal slot and also usable as a larger info-panel image.",
    `Avoid: ${NEGATIVE}.`,
  ].join(" ");
}

const force = process.argv.includes("--force");
const keepRaw = process.argv.includes("--keep-raw");
const onlyArg = process.argv.find((arg) => arg.startsWith("--only="));
const only = onlyArg ? new Set(onlyArg.slice("--only=".length).split(",").map((id) => id.trim())) : null;

const env = loadExternalEnv();
console.log(`Using env file: ${env.path}`);

await fs.mkdir(outputDir, { recursive: true });
await fs.mkdir(rawDir, { recursive: true });

const generated = [];

for (const job of jobs) {
  if (only && !only.has(job.id)) continue;

  const outputPath = path.join(outputDir, job.file);
  const rawPath = path.join(rawDir, job.file.replace("-v1.png", "-source-v1.png"));

  if (!force && await exists(outputPath)) {
    console.log(`skip existing ${job.id}: ${path.relative(projectRoot, outputPath)}`);
    generated.push({ id: job.id, file: path.relative(outputDir, outputPath), skipped: true });
    continue;
  }

  console.log(`generating ${job.id}: ${job.name}`);
  await generateOpenRouterImage({
    env,
    outputPath: rawPath,
    model: MODEL,
    aspectRatio: "1:1",
    imageSize: "1K",
    prompt: buildPrompt(job),
  });

  const alphaPath = `${outputPath}.alpha.png`;
  await removeChromaKeyPng(rawPath, alphaPath, {
    key: [0, 255, 0],
    hardDistance: 62,
    softDistance: 138,
    spill: true,
  });
  await trimTransparentPng(alphaPath, outputPath, 0.16);
  await fs.unlink(alphaPath).catch(() => {});
  if (!keepRaw) await fs.unlink(rawPath).catch(() => {});

  generated.push({
    id: job.id,
    name: job.name,
    file: path.relative(outputDir, outputPath),
    provider: "openrouter",
    model: MODEL,
  });
}

await fs.writeFile(
  manifestPath,
  `${JSON.stringify(
    {
      generated_at: new Date().toISOString(),
      provider: "openrouter",
      model: MODEL,
      key_color: KEY_COLOR,
      assets: generated,
    },
    null,
    2,
  )}\n`,
  "utf8",
);

console.log(`manifest: ${path.relative(projectRoot, manifestPath)}`);
console.log(`icons: ${generated.length}`);

async function exists(targetPath) {
  try {
    await fs.access(targetPath);
    return true;
  } catch {
    return false;
  }
}
