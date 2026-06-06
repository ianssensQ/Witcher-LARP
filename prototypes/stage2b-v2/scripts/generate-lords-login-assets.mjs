import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { loadExternalEnv } from "./lib/env.mjs";
import {
  generateIdeogramImage,
  generateOpenRouterImage,
  generateRecraftImage,
  trimTransparentPng,
} from "./lib/image-providers.mjs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const projectRoot = path.resolve(__dirname, "..");
const outputDir = path.join(projectRoot, "src", "assets", "generated", "lords-login");
const manifestPath = path.join(outputDir, "manifest.json");

const ENTER_TEXT = "\u0412\u0445\u043e\u0434";
const TRAINING_TEXT = "\u041e\u0431\u0443\u0447\u0435\u043d\u0438\u0435";

const STYLE_BRIEF = [
  "dark fantasy strategy game interface",
  "hand painted but production polished",
  "heavy aged iron, cold blue enamel, old gold bevels",
  "deep shadows, visible scratches, carved relief, realistic material depth",
  "Warcraft III Frozen Throne main menu composition as broad inspiration only",
  "The Witcher 3 mood and Heroes of Might and Magic Olden Era fantasy atmosphere",
  "native game UI asset, not website UI",
].join(", ");

const NEGATIVE = [
  "flat web UI",
  "modern SaaS interface",
  "plastic toy chains",
  "neon rectangles",
  "cartoon mobile app buttons",
  "English labels",
  "official Warcraft logo",
  "official Witcher logo",
  "copied trademarked logo",
  "watermark",
  "mockup annotations",
  "Figma frame labels",
  "developer notes",
].join(", ");

const jobs = [
  {
    id: "background",
    file: "login-background.png",
    provider: "openrouter",
    run: (env, outputPath) =>
      generateOpenRouterImage({
        env,
        outputPath,
        model: process.env.OPENROUTER_IMAGE_MODEL || "openai/gpt-5.4-image-2",
        aspectRatio: "16:9",
        imageSize: "2K",
        prompt: [
          "Create a finished 16:9 PC game main menu background, not a website hero image.",
          "Composition: a lonely medieval castle tower and fortified town in the distance, viewed from slightly below, with a cold misty valley, snow haze, broken stone road, black pines, pale moonlight and dim warm windows.",
          "Mood: dark Slavic fantasy, Witcher-like wilderness, Heroes of Might and Magic Olden Era sense of strategic fantasy, but no copied official assets.",
          "Layout constraints: keep the upper-left third visually calmer and darker for a large title logo; keep the right third with enough atmospheric negative space for a hanging metal menu plaque.",
          "Lighting: blue-gray moonlit fog, warm gold torch accents only near the castle, strong atmospheric depth, volumetric mist, painterly but production-polished.",
          "Camera and detail: cinematic matte painting, high-resolution, believable stone, wood, snow, iron and banners; no UI elements, no readable text, no characters in foreground, no rectangular panels.",
          STYLE_BRIEF,
          `Avoid: ${NEGATIVE}.`,
        ].join(" "),
      }),
  },
  {
    id: "logo",
    file: "witcher-larp-logo.png",
    provider: "ideogram",
    run: async (env, outputPath) => {
      await generateIdeogramImage({
        env,
        outputPath,
        endpoint: "/v1/ideogram-v3/generate-transparent",
        aspectRatio: "16x9",
        renderingSpeed: "QUALITY",
        prompt: [
          "Transparent background premium fantasy PC game title logo.",
          "Exact visible title text must be: Witcher LARP I.",
          "The words Witcher LARP are the main readable mark: large medieval serif display lettering, carved ice and aged steel, cold blue inner glow, chipped silver edges, old gold bevel highlights, deep black shadow under every letter.",
          "The Roman numeral I is behind the words, much taller than the title, like a vertical frozen stone monolith or sword-shaped slab; it must feel integrated behind the title rather than typed beside it.",
          "Style target: heavy volumetric strategy game title mark, Warcraft III Frozen Throne type of mass and dimensionality as broad inspiration, but not a copy of any official logo.",
          "Materials: cracked frost, weathered iron, carved stone, subtle gold trim, sharp bevels, deep ambient occlusion, hand-painted fantasy rendering.",
          "Composition: centered transparent PNG asset, no background scenery, no border rectangle, no extra text, no subtitle, no watermark.",
        ].join(" "),
        negativePrompt: [
          NEGATIVE,
          "flat plain font",
          "thin modern typography",
          "website header",
          "unreadable distorted letters",
          "extra words",
          "logo on a card",
          "black or white rectangular background",
        ].join(", "),
      });
      await trimTransparentPng(outputPath, outputPath);
      return { provider: "ideogram", outputPath };
    },
  },
  {
    id: "menu-frame",
    file: "menu-frame.png",
    provider: "recraft",
    run: (env, outputPath) =>
      generateRecraftImage({
        env,
        outputPath,
        size: "1024x1024",
        model: "recraftv3",
        prompt: [
          "Generate one isolated transparent-ready UI asset for a PC fantasy strategy game main menu.",
          "Object: a vertical hanging menu sign with no text and no buttons drawn inside.",
          "Construction: two heavy dark iron chains coming from the top, thick forged links, a dark riveted metal bracket, massive aged iron frame, dark carved oak center panel, cold blue enamel side trims, old gold bevels and studs.",
          "Visual weight: the chains and frame must look heavy, real, slightly dirty, scratched, dented and worn, not plastic or toy-like.",
          "Shape: front-facing with a very slight 3/4 perspective, enough empty wooden interior space for exactly two wide horizontal buttons stacked vertically.",
          "Lighting: dramatic top-left cold moonlight, warm golden edge highlights, deep contact shadows, realistic material depth.",
          "Output constraints: isolated object on plain light neutral background, no readable text, no UI labels, no modern rectangular web panel.",
          STYLE_BRIEF,
          `Avoid: ${NEGATIVE}.`,
        ].join(" "),
        removeBackground: true,
        trimTransparent: true,
      }),
  },
  {
    id: "button-enter",
    file: "button-enter.png",
    provider: "ideogram",
    run: async (env, outputPath) => {
      await generateIdeogramImage({
        env,
        outputPath,
        endpoint: "/v1/ideogram-v3/generate-transparent",
        aspectRatio: "16x9",
        renderingSpeed: "QUALITY",
        prompt: [
          `Transparent background fantasy PC game menu button with exact readable Russian text: ${ENTER_TEXT}.`,
          "The button is a single long horizontal physical object, centered, occupying most of the canvas width.",
          "Readable Cyrillic lettering: large pale silver-gold engraved medieval serif letters, centered on the button, no extra characters.",
          "Surface: dark cold-blue enamel inset, thick raised aged-iron border, old gold bevels, rivets at corners, subtle frosty inner glow, deep shadows below the raised frame.",
          "It must feel like a real object from a Warcraft III style fantasy game menu: heavy, dimensional, scratched, dented, metal and enamel, not a flat web rectangle.",
          "State: normal default button state, not hover, not pressed, no cursor, no surrounding panel.",
          "No English text, no extra words, no background card, no UI mockup annotations.",
          STYLE_BRIEF,
        ].join(" "),
        negativePrompt: [NEGATIVE, "unreadable Cyrillic", "misspelled Russian text"].join(", "),
      });
      await trimTransparentPng(outputPath, outputPath);
      return { provider: "ideogram", outputPath };
    },
  },
  {
    id: "button-training",
    file: "button-training.png",
    provider: "ideogram",
    run: async (env, outputPath) => {
      await generateIdeogramImage({
        env,
        outputPath,
        endpoint: "/v1/ideogram-v3/generate-transparent",
        aspectRatio: "16x9",
        renderingSpeed: "QUALITY",
        prompt: [
          `Transparent background fantasy PC game menu button with exact readable Russian text: ${TRAINING_TEXT}.`,
          "The button is a single long horizontal physical object, centered, occupying most of the canvas width.",
          "Readable Cyrillic lettering: large pale silver-gold engraved medieval serif letters, centered on the button, no extra characters.",
          "Surface: dark cold-blue enamel inset, thick raised aged-iron border, old gold bevels, rivets at corners, subtle frosty inner glow, deep shadows below the raised frame.",
          "It must feel like a real object from a Warcraft III style fantasy game menu: heavy, dimensional, scratched, dented, metal and enamel, not a flat web rectangle.",
          "State: normal default button state, not hover, not pressed, no cursor, no surrounding panel.",
          "No English text, no extra words, no background card, no UI mockup annotations.",
          STYLE_BRIEF,
        ].join(" "),
        negativePrompt: [NEGATIVE, "unreadable Cyrillic", "misspelled Russian text"].join(", "),
      });
      await trimTransparentPng(outputPath, outputPath);
      return { provider: "ideogram", outputPath };
    },
  },
  {
    id: "input-frame",
    file: "input-frame.png",
    provider: "recraft",
    run: (env, outputPath) =>
      generateRecraftImage({
        env,
        outputPath,
        size: "1024x1024",
        model: "recraftv3",
        prompt: [
          "Isolated empty fantasy PC game input frame, transparent-ready on plain light background.",
          "Long horizontal recessed plaque, no text, no icon, no cursor.",
          "Dark carved wood center, aged iron rim, old gold bevel, small rivets, cold blue enamel corner accents, deep inner shadow.",
          "Same kit as hanging sign and buttons: heavy realistic metal and wood, scratches, dents, moonlit edges, not web UI.",
          `Avoid: ${NEGATIVE}.`,
        ].join(" "),
        removeBackground: true,
        trimTransparent: true,
      }),
  },
];

const force = process.argv.includes("--force");
const onlyArg = process.argv.find((arg) => arg.startsWith("--only="));
const only = onlyArg ? new Set(onlyArg.slice("--only=".length).split(",")) : null;

const env = loadExternalEnv();
console.log(`Using env file: ${env.path}`);

await fs.mkdir(outputDir, { recursive: true });

const generated = [];
for (const job of jobs) {
  if (only && !only.has(job.id)) continue;

  const outputPath = path.join(outputDir, job.file);
  const exists = await fileExists(outputPath);

  if (exists && !force) {
    generated.push({ id: job.id, provider: job.provider, file: job.file, skipped: true });
    console.log(`skip ${job.id}: ${job.file}`);
    continue;
  }

  console.log(`generate ${job.id} via ${job.provider}`);
  const result = await job.run(env, outputPath);
  generated.push({ id: job.id, provider: result.provider, file: job.file, skipped: false });
}

await fs.writeFile(
  manifestPath,
  `${JSON.stringify(
    {
      screen: "lords-login",
      generatedAt: new Date().toISOString(),
      sourceEnv: env.path,
      assets: generated,
      notes:
        "Runtime React should position these as image layers; CSS should not paint the metal, chains, logo, or button surfaces.",
    },
    null,
    2,
  )}\n`,
);

console.log(`manifest: ${manifestPath}`);

async function fileExists(targetPath) {
  try {
    await fs.access(targetPath);
    return true;
  } catch {
    return false;
  }
}
