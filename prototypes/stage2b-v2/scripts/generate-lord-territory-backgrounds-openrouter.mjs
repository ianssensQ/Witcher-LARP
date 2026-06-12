import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { loadExternalEnv } from "./lib/env.mjs";
import { ensurePngFile, generateOpenRouterImage } from "./lib/image-providers.mjs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.resolve(__dirname, "..");
const assetDir = path.join(projectRoot, "src", "assets", "generated", "lords-home", "territories");

const model = process.env.OPENROUTER_IMAGE_MODEL || "openai/gpt-5.4-image-2";
const env = loadExternalEnv();

const sharedPrompt = [
  "Create one original 16:9 wide territory home background for a browser fantasy strategy game.",
  "Match the accepted existing lord territory backgrounds: high-detail painterly realism, elevated three-quarter game camera, dark Slavic/continental medieval fantasy, tactical but cinematic, usable as a full-screen game UI background.",
  "Composition constraints: no text, no labels, no logos, no watermark, no UI frames, no large foreground character, no copied official Witcher, Warcraft, Heroes or Gwent art, symbols or architecture.",
  "Layout constraints for live UI overlay: keep the top 12 percent readable, keep the bottom 25 percent calmer and darker for army/garrison/recruit lanes, keep the left and right edges less busy for action docks and territory bubbles.",
  "Use a strong mid-ground landmark in the upper middle or upper right, with readable paths, palisades, huts, bridges, water, rocks or trees according to the territory.",
  "Lighting: cinematic natural light with torch or magical accent points, painterly atmosphere, crisp enough for 2K UI asset use.",
].join(" ");

const territoryJobs = [
  {
    id: "territory_fort_west",
    filename: "territory-home-west-ostrog-v1.png",
    scene:
      "Western wooden ostrog on a pine foothill ridge, dark timber palisades, two watchtowers, winding muddy road, distant low mountains, cold dusk and warm torchlight, distinct from a snowy northern fort.",
  },
  {
    id: "territory_fort_southwest",
    filename: "territory-home-southwest-krep-v1.png",
    scene:
      "Southwestern rough stone-and-timber keep over a rocky ravine, compact defensive yard, siege beams, banner poles without emblems, stormy sunset clouds, ochre rock and dark spruce.",
  },
  {
    id: "territory_field_west_large",
    filename: "territory-home-west-pashni-v1.png",
    scene:
      "Wide left-bank farmland, golden oat fields, granaries, harvest carts, irrigation ditch, dirt roads, low watch post on a hill, broad cloudy sky and late afternoon light.",
  },
  {
    id: "territory_field_east_large",
    filename: "territory-home-east-pashni-v1.png",
    scene:
      "Eastern green mustering fields and recruit pasture, canvas tents, archery stakes, training lanes, fenced plots, supply sheds, morning haze and clean readable paths.",
  },
  {
    id: "territory_village_barn",
    filename: "territory-home-hay-posad-v1.png",
    scene:
      "Small hay-barn village, thatched barns, stacked hay, muddy village square, smoke from chimneys, rough fences, a modest palisade and warm evening windows.",
  },
  {
    id: "territory_village_east_shed",
    filename: "territory-home-east-sloboda-v1.png",
    scene:
      "Eastern sloboda of timber sheds and workshops, blacksmith yard, animal pens suggested by fences only, drying racks, clay road, pale morning mist and practical village clutter.",
  },
  {
    id: "territory_well_city",
    filename: "territory-home-well-market-v1.png",
    scene:
      "Resource market town around a monumental stone well and cistern, merchant stalls, hoists, barrels, stone steps, low aqueduct fragments, gold-gray sunlight after rain.",
  },
  {
    id: "territory_magic_corner",
    filename: "territory-home-magic-corner-v1.png",
    scene:
      "Enclosed magical courtyard with arched stone walls, observatory balcony, alchemy tables, violet-blue rune light, cypress-like silhouettes, twilight and controlled arcane glow.",
  },
  {
    id: "territory_science_barn",
    filename: "territory-home-science-manufactory-v1.png",
    scene:
      "Two-story timber barn manufactory, waterwheel, cranes, gears, workbenches, canvas awnings, smoke vents, greenish workshop lamps, pragmatic research outpost in a rural yard.",
  },
  {
    id: "territory_forest_dark",
    filename: "territory-home-dark-grove-v1.png",
    scene:
      "Dark herbalist grove, old black pines, root-wrapped stone altar, small huts among roots, blue-green herb lights, narrow forest paths, misty and secretive but readable.",
  },
  {
    id: "territory_forest_south_garden",
    filename: "territory-home-south-garden-v1.png",
    scene:
      "Lower southern garden and overgrown orchard, medicinal herb beds, small shrine, trellises, broken stone paths, forest edge, soft sun shafts and a calmer green-gold mood.",
  },
  {
    id: "territory_lake_south_pond",
    filename: "territory-home-south-pond-v1.png",
    scene:
      "Southern moonlit pond settlement, wooden docks, reed beds, stilt huts, lantern reflections, small boats tied to posts, silvery water and gentle fog, distinct from a bleak swamp.",
  },
  {
    id: "territory_swamp_black",
    filename: "territory-home-black-mire-v1.png",
    scene:
      "Black mire raid-cover territory, crooked boardwalks, leaning watch hut, half-sunken fences, dark water, reeds, cyan marsh lights, heavy night fog and dangerous wet ground.",
  },
  {
    id: "territory_mountain_north_alpine",
    filename: "territory-home-north-alpine-ridge-v1.png",
    scene:
      "High northern alpine ridge and fortified pass, snow patches, stone watchtower, rope bridges, stacked supplies, sheer peaks, pale sunrise and sharp cold air.",
  },
  {
    id: "territory_mountain_gray",
    filename: "territory-home-gray-watch-v1.png",
    scene:
      "Gray mountain watch overlook, foggy cliffs, signal beacon tower, terraced stone platforms, worn stairs, wind-torn banners without readable symbols, blue-gray storm light.",
  },
  {
    id: "territory_mountain_west_alpine",
    filename: "territory-home-west-cliffs-v1.png",
    scene:
      "Western jagged alpine cliffs, abandoned mine mouth, pine shelf road, timber lift, rough fort camp, red dusk clouds on stone, strong vertical rock silhouettes.",
  },
];

const onlyArg = process.argv.find((arg) => arg.startsWith("--only="));
const force = process.argv.includes("--force");
const only = onlyArg
  ? new Set(onlyArg.slice("--only=".length).split(",").map((item) => item.trim()).filter(Boolean))
  : null;
const concurrencyArg = process.argv.find((arg) => arg.startsWith("--concurrency="));
const concurrency = Math.max(1, Math.min(4, Number(concurrencyArg?.slice("--concurrency=".length) || 1)));

const selectedJobs = territoryJobs.filter((job) => {
  if (only && !only.has(job.id) && !only.has(job.filename)) {
    return false;
  }
  return true;
});

const pendingJobs = [];
for (const job of selectedJobs) {
  const outputPath = path.join(assetDir, job.filename);
  if (!force && await exists(outputPath)) {
    console.log(`skip existing ${job.id}: ${outputPath}`);
    continue;
  }
  pendingJobs.push({ ...job, outputPath });
}

const errors = [];
let nextIndex = 0;

await Promise.all(
  Array.from({ length: Math.min(concurrency, pendingJobs.length) }, async () => {
    while (nextIndex < pendingJobs.length) {
      const job = pendingJobs[nextIndex];
      nextIndex += 1;
      try {
        await generateJob(job);
      } catch (error) {
        errors.push({ job, error });
      }
    }
  }),
);

if (errors.length > 0) {
  for (const { job, error } of errors) {
    console.error(`failed ${job.id}: ${error.message}`);
  }
  throw new Error(`Failed to generate ${errors.length} territory background(s)`);
}

async function generateJob(job) {
  console.log(`generate ${job.id} via ${model}`);
  await generateOpenRouterImage({
    env,
    outputPath: job.outputPath,
    model,
    aspectRatio: "16:9",
    imageSize: "2K",
    prompt: `${sharedPrompt} Territory identity: ${job.scene}`,
  });
  await ensurePngFile(job.outputPath);
  console.log(`saved ${job.id}: ${job.outputPath}`);
}

async function exists(filePath) {
  try {
    await fs.access(filePath);
    return true;
  } catch {
    return false;
  }
}
