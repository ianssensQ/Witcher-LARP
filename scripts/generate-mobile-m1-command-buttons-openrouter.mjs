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
const model = process.env.OPENROUTER_IMAGE_MODEL || "openai/gpt-5.4-image-2";
const imageSize = process.env.OPENROUTER_M1_BUTTON_IMAGE_SIZE || "1K";
const env = loadExternalEnv();

const buttonJobs = [
  {
    id: "qr",
    file: "command-button-qr-v1.png",
    shape: "wide top-row button insert, compact horizontal octagonal rectangle",
    aspectRatio: "4:3",
    motif: "subtle scan-corner relief in the upper half, like four small brass corner brackets, not a readable QR code",
  },
  {
    id: "orders",
    file: "command-button-orders-v1.png",
    shape: "wide top-row button insert, compact horizontal octagonal rectangle",
    aspectRatio: "4:3",
    motif: "subtle contract-board relief in the upper half: folded parchment edge and two tiny rivets, no text",
  },
  {
    id: "trade",
    file: "command-button-trade-v1.png",
    shape: "wide top-row button insert, compact horizontal octagonal rectangle",
    aspectRatio: "4:3",
    motif: "subtle exchange relief in the upper half: two worn coins and a faint curved metal arrow shape, no letters",
  },
  {
    id: "bag",
    file: "command-button-bag-v1.png",
    shape: "small bottom-row button insert, near-square octagonal rectangle",
    aspectRatio: "1:1",
    motif: "small satchel clasp relief in the upper half, leather and brass, no text",
  },
  {
    id: "gwent",
    file: "command-button-gwent-v1.png",
    shape: "small bottom-row button insert, near-square octagonal rectangle",
    aspectRatio: "1:1",
    motif: "small playing-card corner relief in the upper half, antique brass diamond inlay, no suits or letters",
  },
  {
    id: "pvp",
    file: "command-button-pvp-v1.png",
    shape: "small bottom-row button insert, near-square octagonal rectangle",
    aspectRatio: "1:1",
    motif: "small crossed blade scratch relief in the upper half, dark steel, no text",
  },
  {
    id: "sync",
    file: "command-button-sync-v1.png",
    shape: "small bottom-row button insert, near-square octagonal rectangle",
    aspectRatio: "1:1",
    motif: "small signal rune relief in the upper half: circular brass ring with two short wave marks, no letters",
  },
];

function buildPrompt(job) {
  return [
    "Create one isolated mobile RPG command button insert on a pure flat chroma green background (#00ff00).",
    `Object: ${job.shape}.`,
    "This is only the removable clickable insert that will sit inside an already drawn shared command panel socket; do not draw the surrounding panel, tray, background, or neighboring buttons.",
    "The button should be front-facing, centered, fully visible, with generous chroma margin and transparent-safe edges.",
    "Visual grammar: dark aged leather button face, blackened forged iron rim, muted antique brass bevels and corner plates, tiny rivets, slight raised edge, subtle inner shadow.",
    `Unique action detail: ${job.motif}.`,
    "Reserve the lower third of the button face as a calm darker band for live Godot label text placed later; do not put detail there.",
    "Style: original Slavic dark fantasy monster-hunter journal interface, polished mobile game HUD, restrained, readable, not cluttered.",
    "Lighting: soft top-left torch glint, deep rim shadows, high contrast against the socket but not bright orange.",
    "No readable text, no letters, no numbers, no labels, no logos, no official Witcher medallion, no watermark, no annotations.",
    "Do not use #00ff00 inside the button itself.",
  ].join(" ");
}

await fs.mkdir(assetDir, { recursive: true });

const onlyArg = process.argv.find((arg) => arg.startsWith("--only="));
const only = onlyArg
  ? new Set(onlyArg.slice("--only=".length).split(",").map((value) => value.trim()).filter(Boolean))
  : null;

for (const job of buttonJobs) {
  if (only && !only.has(job.id)) {
    continue;
  }

  const rawPath = path.join(assetDir, `${job.file.replace(/\.png$/, "")}.openrouter-raw.png`);
  const outputPath = path.join(assetDir, job.file);

  console.log(`generate ${job.id} button via ${model}, ${job.aspectRatio}, ${imageSize}`);
  await generateOpenRouterImage({
    env,
    outputPath: rawPath,
    model,
    aspectRatio: job.aspectRatio,
    imageSize,
    prompt: buildPrompt(job),
  });
  await removeChromaKeyPng(rawPath, outputPath, {
    hardDistance: 105,
    softDistance: 175,
  });
  await fs.unlink(rawPath).catch(() => {});
  await fs.unlink(`${rawPath}.openrouter-response.json`).catch(() => {});
  console.log(`saved ${job.id} button: ${outputPath}`);
}
