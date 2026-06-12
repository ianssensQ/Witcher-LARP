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
    subject: "a compact training yard icon, not a wide yard: one central straw practice dummy, small weapon rack, low palisade posts, trampled dirt base, red-brown military accents, chunky clear silhouette for a tiny game tech-tree slot",
  },
  {
    id: "b_barracks",
    file: "building-barracks-v1.png",
    name: "Barracks",
    subject: "a compact barracks icon, not a long hall: squat dark timber and stone guardhouse, shields by a central door, short red-brown banners without symbols, heavy roof beams, chunky clear silhouette for a tiny game tech-tree slot",
  },
  {
    id: "b_archery_range",
    file: "building-archery-range-v1.png",
    name: "Archery Range",
    subject: "a compact archery range icon, not a long field: one small pavilion with bow rack, two close round practice targets, short fence, leather and red-brown military accents, chunky clear silhouette for a tiny game tech-tree slot",
  },
  {
    id: "b_stables",
    file: "building-stables-v1.png",
    name: "Stables",
    subject: "a compact front-facing stable icon: squat timber-and-stone stable with one wide arched stall door, small hay bales, a horseshoe crest without text, chunky readable silhouette, warm lit edges, red-brown accents, not a long barn",
  },
  {
    id: "b_siege_yard",
    file: "building-siege-yard-v1.png",
    name: "Siege Yard",
    subject: "a compact front-facing siege yard icon: chunky timber ballista on a short stone plinth, small crane arm, stacked bolts and beams, broad readable silhouette, warm lit edges, red-brown military accents, not tall or dark",
  },
  {
    id: "b_war_academy",
    file: "building-war-academy-v1.png",
    name: "War Academy",
    subject: "a compact front-facing war academy icon: squat stone drill hall with a shield-shaped arched gate, two short towers, plain training standards without symbols, broad readable silhouette, warm lit edges, disciplined red-brown military accents",
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
    subject: "a compact treasury hall icon, not a long building: one central heavy coffer, two short stone columns, guarded squat vault arch, warm gold metal highlights, chunky clear silhouette for a tiny game tech-tree slot",
  },
  {
    id: "b_notice_board",
    file: "building-notice-board-v1.png",
    name: "Notice Board",
    subject: "a compact front-facing notice board icon: stout timber notice board under a small roof, pinned blank parchment sheets, wax seals, muted brass trim, parchment accents, chunky readable silhouette for a tiny game tech-tree slot, no readable text",
  },
  {
    id: "b_envoy_hall",
    file: "building-envoy-hall-v1.png",
    name: "Envoy Hall",
    subject: "a compact front-facing envoy hall icon: squat diplomatic timber-and-stone hall, central arched doorway, two short blank banners, sealed scroll tubes, polished dark wood, parchment and muted brass accents, chunky readable silhouette, no symbols or text",
  },
  {
    id: "b_map_room",
    file: "building-map-room-v1.png",
    name: "Map Room",
    subject: "a compact front-facing map room icon: squat cartography chamber with a round map table visible through an arched opening, large compass, rolled blank maps, small lantern, parchment and brass accents, chunky readable silhouette, no readable markings",
  },
  {
    id: "b_raid_office",
    file: "building-raid-office-v1.png",
    name: "Raid Office",
    subject: "a compact front-facing raid office icon: squat tent-and-timber command hut with a small war table visible through an arched opening, blank route map, dagger markers, parchment and muted brass accents, chunky readable silhouette, not a wide interior scene",
  },
  {
    id: "b_war_council",
    file: "building-war-council-v1.png",
    name: "War Council",
    subject: "a compact front-facing war council icon: squat dark wood council hall with a round command table behind a broad arched entrance, two miniature blank banners, candles, parchment and muted brass accents, chunky readable silhouette, no symbols or text",
  },
  {
    id: "b_mage_study",
    file: "building-mage-study-v1.png",
    name: "Mage Study",
    subject: "a compact mage study icon, not a tall tower: squat arched study nook, stacked books, crystal focus on a desk, small roof spire only, cold violet arcane highlights, chunky clear silhouette for a tiny game tech-tree slot, no runic text",
  },
  {
    id: "b_alchemy_lab",
    file: "building-alchemy-lab-v1.png",
    name: "Alchemy Lab",
    subject: "a compact alchemy laboratory icon, not a long building: stone workbench, large alembic, a few glass flasks, small cauldron, cold violet and amber magical highlights, chunky clear silhouette for a tiny game tech-tree slot, no labels",
  },
  {
    id: "b_scrying_room",
    file: "building-scrying-room-v1.png",
    name: "Scrying Room",
    subject: "a compact scrying room icon, not a tall tower: squat stone alcove, central crystal orb on a short crescent stand, dark mirror behind it, three small candles, cold violet magical glow, chunky clear silhouette for a tiny game tech-tree slot, no written symbols",
  },
  {
    id: "b_wards",
    file: "building-wards-v1.png",
    name: "Wards",
    subject: "a compact warding shrine icon, not a long monument: three short stone obelisks around protective metal rings, small glowing violet barrier facets, old candles at the base, chunky clear silhouette for a tiny game tech-tree slot, no readable runes",
  },
  {
    id: "b_ritual_chamber",
    file: "building-ritual-chamber-v1.png",
    name: "Ritual Chamber",
    subject: "a compact ritual chamber icon, not a long hall: low stone altar under a short arched canopy, candle circle, suspended crystal over a dark carved slab, deep violet arcane highlights, chunky clear silhouette for a tiny game tech-tree slot, no readable symbols",
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
