import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { loadExternalEnv } from "../prototypes/stage2b-v2/scripts/lib/env.mjs";
import {
  generateOpenRouterImage,
  removeChromaKeyPng,
} from "../prototypes/stage2b-v2/scripts/lib/image-providers.mjs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, "..");
const assetDir = path.join(repoRoot, "mobile", "assets", "ui", "witcher", "m1_journal");
const rawPath = path.join(assetDir, "command-panel-v1.openrouter-raw.png");
const outputPath = path.join(assetDir, "command-panel-v1.png");

const model = process.env.OPENROUTER_IMAGE_MODEL || "openai/gpt-5.4-image-2";
const aspectRatio = process.env.OPENROUTER_M1_PANEL_ASPECT_RATIO || "16:9";
const imageSize = process.env.OPENROUTER_M1_PANEL_IMAGE_SIZE || "1K";
const env = loadExternalEnv();

const prompt = [
  "Create one isolated mobile game UI command panel asset on a pure flat chroma green background (#00ff00).",
  "The output is a single shared backing frame for a 390x844 phone screen bottom area, no separate floating cards.",
  "Composition: a wide horizontal dark fantasy tray, front-facing, symmetric, with exactly seven empty recessed button sockets.",
  "Socket layout: top row has three larger sockets, evenly spaced; bottom row has four smaller sockets, evenly spaced.",
  "All seven sockets must use the same visual grammar: carved dark leather center, blackened iron bevel, worn brass edge, tiny rivets, subtle inner shadow.",
  "Leave each socket empty and readable for live text/icons placed later by the game engine.",
  "Materials: dark aged leather, blackened forged iron, muted antique brass, slightly scratched, game-ready, not photoreal UI kit.",
  "Style: original Slavic dark fantasy monster-hunter journal interface, premium mobile RPG HUD, restrained and not cluttered.",
  "Lighting: soft top-left warm torch glints, deep inner shadows, high contrast between empty sockets and the backing frame.",
  "Shape: one continuous panel frame with connected rails and shared outer border; it must look like one object, not seven separate buttons.",
  "No readable text, no letters, no numbers, no icons, no symbols, no logos, no official Witcher medallion, no watermark, no annotations.",
  "Keep generous transparent/chroma margin around the object, but make the panel fill most of the canvas width.",
].join(" ");

await fs.mkdir(assetDir, { recursive: true });
console.log(`generate mobile M1 command panel via ${model}, ${aspectRatio}, ${imageSize}`);
await generateOpenRouterImage({
  env,
  outputPath: rawPath,
  model,
  aspectRatio,
  imageSize,
  prompt,
});
await removeChromaKeyPng(rawPath, outputPath, {
  hardDistance: 105,
  softDistance: 175,
});
console.log(`saved command panel: ${outputPath}`);
