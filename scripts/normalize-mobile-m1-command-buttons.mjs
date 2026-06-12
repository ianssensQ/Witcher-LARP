import path from "node:path";
import { fileURLToPath } from "node:url";
import { trimTransparentPng } from "../prototypes/stage2b-v2/scripts/lib/image-providers.mjs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, "..");
const assetDir = path.join(repoRoot, "mobile", "assets", "ui", "witcher", "m1_journal");

const buttonFiles = [
  "command-button-qr-v1.png",
  "command-button-orders-v1.png",
  "command-button-trade-v1.png",
  "command-button-bag-v1.png",
  "command-button-gwent-v1.png",
  "command-button-pvp-v1.png",
  "command-button-sync-v1.png",
];

for (const file of buttonFiles) {
  const filePath = path.join(assetDir, file);
  await trimTransparentPng(filePath, filePath, 0);
  console.log(`normalized transparent bounds: ${filePath}`);
}
