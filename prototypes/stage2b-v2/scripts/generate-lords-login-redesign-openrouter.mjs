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
const assetDir = path.join(projectRoot, "src", "assets", "generated", "lords-login");

const model = process.env.OPENROUTER_IMAGE_MODEL || "openai/gpt-5.4-image-2";
const env = loadExternalEnv();

const jobs = {
  background: async () => {
    const outputPath = path.join(assetDir, "login-background-warcraft.png");
    await generateOpenRouterImage({
      env,
      outputPath,
      model,
      aspectRatio: "16:9",
      imageSize: "2K",
      prompt: [
        "Create a finished 16:9 PC game main menu background for a dark fantasy strategy game.",
        "Composition reference: Warcraft III Frozen Throne main menu feeling, but no copied assets and no official logos.",
        "Scene: one dominant lonely gothic-medieval castle tower on a steep frozen rock ridge in the middle-left distance, with a smaller fortified town below, black pines, mountain silhouettes, broken stone bridge, pale moon or blue magical glow behind the tower.",
        "Mood: cold, misty, ominous, Slavic dark fantasy, Witcher-like wilderness, not cheerful city builder.",
        "Lighting: blue-gray snow fog, heavy atmospheric haze, distant warm torch dots only, strong silhouette, soft volumetric light, deep dark edges.",
        "Layout constraints for UI: keep the upper-left quadrant readable for an existing logo; keep the right third darker and calmer for a hanging menu panel; do not put important architecture behind the right menu area.",
        "Camera: low cinematic view, slight upward angle, large empty air and fog, less detail than a town panorama, more iconic tower silhouette.",
        "Quality: high-end hand-painted game menu background, painterly realism, 2K detail, no text, no UI, no characters in foreground, no frames, no buttons, no labels, no watermark.",
      ].join(" "),
    });
    console.log(`saved background: ${outputPath}`);
  },

  panel: async () => {
    const rawPath = path.join(assetDir, "menu-frame-warcraft.raw.png");
    const outputPath = path.join(assetDir, "menu-frame-warcraft.png");
    await generateOpenRouterImage({
      env,
      outputPath: rawPath,
      model,
      aspectRatio: "1:1",
      imageSize: "1K",
      prompt: [
        "Create one isolated PC fantasy game menu panel asset on a pure flat chroma green background (#00ff00).",
        "The panel must be fully visible with generous margin; do not crop any chain, hook, corner, rod or bottom edge.",
        "Composition reference: Warcraft III Frozen Throne right-side hanging menu plaque, but original design, not a copy.",
        "Object: front-facing vertical suspended menu panel with two heavy black iron chains at the top, short hooks, massive dark forged iron top bar, rectangular dark metal-and-wood body, no perspective turn, no side rotation.",
        "Style: much darker and heavier than a tavern sign; grim blackened iron, scratched gunmetal, cold blue enamel insets, old gold worn bevels, rivets, dents, soot, frost and deep contact shadows.",
        "Button integration: inside the panel create exactly two empty recessed horizontal slots stacked vertically, sized for existing wide button sprites. The slots must look carved into the panel, with inner shadow and subtle blue-gold bevel, but no text.",
        "Do not draw the button words. Do not draw any readable text. No extra panels, no decorative flowers, no cute shapes.",
        "Lighting: same cold moonlit fantasy style as icy blue/gold buttons, top-left light, strong ambient occlusion, realistic material depth.",
        "Output: centered single object, chroma green background only, no floor shadow outside object, no watermark, no annotations.",
      ].join(" "),
    });
    await removeChromaKeyPng(rawPath, outputPath);
    await trimTransparentPng(outputPath, outputPath, 0.03);
    console.log(`saved panel: ${outputPath}`);
  },
};

const onlyArg = process.argv.find((arg) => arg.startsWith("--only="));
const only = onlyArg ? onlyArg.slice("--only=".length).split(",") : Object.keys(jobs);

for (const name of only) {
  const job = jobs[name];
  if (!job) {
    throw new Error(`Unknown job: ${name}`);
  }
  console.log(`generate ${name} via ${model}`);
  await job();
}
