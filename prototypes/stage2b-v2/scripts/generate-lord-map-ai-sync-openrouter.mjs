import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { loadExternalEnv } from "./lib/env.mjs";
import { generateOpenRouterImage } from "./lib/image-providers.mjs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const prototypeRoot = path.resolve(__dirname, "..");
const repoRoot = path.resolve(prototypeRoot, "..", "..");
const prefix = process.env.LORD_MAP_AI_SYNC_PREFIX || "lord_map_ai_sync_v1";
const promptPath = path.join(repoRoot, "reports", "map-debug-crops", `${prefix}-openrouter-prompt.md`);
const outputPath = path.join(
  repoRoot,
  "backend",
  "witcher_larp",
  "web",
  "lord",
  "assets",
  `${prefix}_openrouter_raw.png`,
);

const model = process.env.OPENROUTER_IMAGE_MODEL || "openai/gpt-5.4-image-2";
const aspectRatio = process.env.OPENROUTER_IMAGE_ASPECT_RATIO || "3:2";
const imageSize = process.env.OPENROUTER_IMAGE_SIZE || "4K";
const env = loadExternalEnv();
const prompt = await fs.readFile(promptPath, "utf8");

console.log(`generate lord map raw via ${model}, ${aspectRatio}, ${imageSize}`);
await generateOpenRouterImage({
  env,
  outputPath,
  model,
  aspectRatio,
  imageSize,
  prompt,
});
console.log(`saved raw map: ${outputPath}`);
