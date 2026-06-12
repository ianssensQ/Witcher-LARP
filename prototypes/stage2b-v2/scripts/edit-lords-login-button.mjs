import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { loadExternalEnv } from "./lib/env.mjs";
import { editIdeogramImage, trimTransparentPng } from "./lib/image-providers.mjs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.resolve(__dirname, "..");
const assetDir = path.join(projectRoot, "src", "assets", "generated", "lords-login");

const sourcePath = path.join(assetDir, "button-enter.png");
const outputPath = path.join(assetDir, "button-training.png");
const trainingText = "\u041e\u0431\u0443\u0447\u0435\u043d\u0438\u0435";

const env = loadExternalEnv();

await fs.access(sourcePath);

console.log("edit button-enter into button-training via ideogram");
await editIdeogramImage({
  env,
  inputPath: sourcePath,
  outputPath,
  aspectRatio: "16x9",
  prompt: [
    `Use the provided button image as the exact visual reference. Replace only the visible Russian text with: ${trainingText}.`,
    "Keep the button shape, proportions, border silhouette, dark blue icy enamel surface, gold bevels, cracked stone-metal texture, rivets, scratches, black ink shadows, lighting direction, thickness and overall rendering style identical to the reference image.",
    "The new Cyrillic word must be centered, large, readable, and engraved or raised in the same pale silver-gold fantasy lettering style as the original.",
    "Do not redesign the button. Do not change the frame, corners, colors, materials, camera angle, canvas framing or background transparency.",
    "Transparent PNG game UI sprite, no extra words, no English text, no cursor, no surrounding panel.",
  ].join(" "),
});

await trimTransparentPng(outputPath, outputPath);
console.log(`saved: ${outputPath}`);
