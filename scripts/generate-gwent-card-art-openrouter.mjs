import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, "..");
const envFile = process.env.WITCHER_ASSET_ENV || "";
const externalEnv = envFile ? await loadEnvFile(envFile) : {};

const cardId = envValue("GWENT_CARD_ID") || "rare_gwent_02";
if (!/^[A-Za-z0-9_]+$/.test(cardId)) {
  throw new Error("GWENT_CARD_ID must use only letters, numbers and underscores. The iOS UI maps art by card_id.");
}

const assetName = envValue("GWENT_ASSET_NAME") || `gwent_card_art_${cardId}`;
const imageSetDir = path.join(repoRoot, "ios", "Resources", "Assets.xcassets", `${assetName}.imageset`);
const outputPath = path.join(imageSetDir, `${assetName}.png`);
const artifactDir = path.join(repoRoot, "artifacts", "openrouter");
const responsePath = path.join(artifactDir, `${assetName}.response.json`);
const promptPath = path.join(artifactDir, `${assetName}.prompt.txt`);
const catalogPath = path.resolve(repoRoot, envValue("GWENT_CARD_CATALOG") || "data/seed/gwent_cards.csv");
const cardMeta = await loadCatalogCard(catalogPath, cardId);

const cardTitle = envValue("GWENT_CARD_TITLE") || cardMeta?.display_name || readableIdentifier(cardId);
const cardRow = envValue("GWENT_CARD_ROW") || cardMeta?.row || "";
const cardType = envValue("GWENT_CARD_TYPE") || cardMeta?.type || "";
const cardFaction = envValue("GWENT_CARD_FACTION") || cardMeta?.faction || "";
const cardStrength = envValue("GWENT_CARD_STRENGTH") || cardMeta?.strength || "";
const cardEffect = envValue("GWENT_CARD_EFFECT") || cardMeta?.effect || "";
const cardRarity = envValue("GWENT_CARD_RARITY") || cardMeta?.rarity || "";
const effectText = envValue("GWENT_CARD_EFFECT_TEXT") || cardMeta?.effect_text || "";
const cardSubject = envValue("GWENT_CARD_SUBJECT") || defaultSubject({
  title: cardTitle,
  row: cardRow,
  type: cardType,
  effect: cardEffect,
  faction: cardFaction,
});
const cardScene = envValue("GWENT_CARD_SCENE") || defaultScene(cardRow, cardEffect);
const extraStyle = envValue("GWENT_CARD_STYLE");
const extraAvoid = envValue("GWENT_CARD_AVOID");

const prompt = buildPrompt({
  cardId,
  cardTitle,
  cardRow,
  cardType,
  cardFaction,
  cardStrength,
  cardEffect,
  cardRarity,
  effectText,
  cardSubject,
  cardScene,
  extraStyle,
  extraAvoid,
});

await fs.mkdir(artifactDir, { recursive: true });
await fs.writeFile(promptPath, `${prompt}\n`);

if (envFlag("GWENT_DRY_RUN")) {
  console.log(`dry-run ${assetName}`);
  console.log(`prompt ${promptPath}`);
  console.log(`output ${outputPath}`);
  console.log(prompt);
  process.exit(0);
}

const model = envValue("OPENROUTER_IMAGE_MODEL") || "openai/gpt-5.4-image-2";
const baseUrl = (envValue("OPENROUTER_BASE_URL") || "https://openrouter.ai/api/v1").replace(/\/$/, "");
const apiKey = envValue("OPENROUTER_API_KEY");

if (!apiKey) {
  throw new Error("OPENROUTER_API_KEY is required to generate Gwent card art.");
}

await fs.mkdir(imageSetDir, { recursive: true });

console.log(`generate ${assetName} via ${model}`);
const response = await fetch(`${baseUrl}/chat/completions`, {
  method: "POST",
  headers: {
    Authorization: `Bearer ${apiKey}`,
    "Content-Type": "application/json",
    "HTTP-Referer": envValue("OPENROUTER_HTTP_REFERER") || "http://127.0.0.1:8002",
    "X-Title": envValue("OPENROUTER_APP_TITLE") || "Witcher LARP Gwent card art",
  },
  body: JSON.stringify({
    model,
    messages: [{ role: "user", content: prompt }],
    modalities: ["image", "text"],
    image_config: {
      aspect_ratio: "3:4",
      image_size: envValue("OPENROUTER_IMAGE_SIZE") || "1K",
    },
    stream: false,
  }),
  signal: AbortSignal.timeout(240_000),
});

const text = await response.text();
await fs.writeFile(responsePath, text);
if (!response.ok) {
  throw new Error(`OpenRouter request failed ${response.status}: ${text.slice(0, 1200)}`);
}

const data = JSON.parse(text);
const image = data.choices?.[0]?.message?.images?.[0];
const dataUrl = image?.image_url?.url || image?.imageUrl?.url;
if (!dataUrl) {
  throw new Error(`OpenRouter response did not include an image. Response saved to ${responsePath}`);
}

if (/^https?:\/\//i.test(dataUrl)) {
  const imageResponse = await fetch(dataUrl, { signal: AbortSignal.timeout(120_000) });
  if (!imageResponse.ok) {
    throw new Error(`Image download failed ${imageResponse.status}`);
  }
  await fs.writeFile(outputPath, Buffer.from(await imageResponse.arrayBuffer()));
} else {
  const base64 = dataUrl.replace(/^data:image\/[a-z0-9.+-]+;base64,/i, "");
  await fs.writeFile(outputPath, Buffer.from(base64, "base64"));
}

await fs.writeFile(
  path.join(imageSetDir, "Contents.json"),
  `${JSON.stringify(
    {
      images: [
        {
          filename: `${assetName}.png`,
          idiom: "universal",
        },
      ],
      info: {
        author: "xcode",
        version: 1,
      },
    },
    null,
    2,
  )}\n`,
);

console.log(`saved ${outputPath}`);
console.log(`prompt ${promptPath}`);

function buildPrompt({
  cardId,
  cardTitle,
  cardRow,
  cardType,
  cardFaction,
  cardStrength,
  cardEffect,
  cardRarity,
  effectText,
  cardSubject,
  cardScene,
  extraStyle,
  extraAvoid,
}) {
  return [
    "Use case: stylized-concept",
    "Asset type: vertical fantasy trading-card portrait art for a mobile card game.",
    `Primary request: create an original illustration for card ${cardId} / "${cardTitle}".`,
    `Card gameplay metadata: faction ${cardFaction || "unknown"}, row ${cardRow || "unknown"}, type ${cardType || "unknown"}, strength ${cardStrength || "n/a"}, effect ${cardEffect || "none"}, rarity ${cardRarity || "unknown"}.`,
    effectText ? `Readable effect: ${effectText}` : "",
    "Important IP rule: the art direction may feel like grim Slavic dark fantasy monster-hunter fiction, but the image must be original and must not depict or copy any existing franchise character, actor, costume, logo, medallion, symbol, screenshot, or official card art.",
    `Subject: ${cardSubject}`,
    "Composition: vertical 3:4 portrait, centered upper-body-to-thigh framing for characters or centered object/scene framing for specials, strong readable shape at tiny mobile-card size, no frame and no border.",
    "Card crop safety hard rule: the full head, hair, forehead, ears and shoulders must be completely visible with generous empty fog/forest/sky space above the highest hair for any character. Place character eyes around the upper third, not at the very top. The top 18% of the image must remain safe atmospheric background; no hair, scalp, sword tip, banner top or face may touch the top edge.",
    "Mobile crop rule: the app top-aligns this art inside short card windows and crops overflow only from the bottom. If anything must be lost, crop only lower body, hands, belt, object base or cloak bottom; never crop head, face, hair, shoulders, main object silhouette, weapon hilt or banner top.",
    `Scene: ${cardScene}`,
    [
      "Style: high-end painterly collectible card art, gritty, elegant, cinematic, sharp focal subject, textured brushwork, dramatic contrast.",
      extraStyle,
    ].filter(Boolean).join(" "),
    [
      "Avoid: text, letters, numbers, watermark, logo, UI, border, frame, gore, extra characters, close-up face crop, cropped scalp, hair touching the top edge, exact Witcher/Geralt/CDPR/Gwent likeness, wolf medallion, white wolf emblem.",
      extraAvoid,
    ].filter(Boolean).join(" "),
  ].filter(Boolean).join("\n");
}

function defaultSubject({ title, row, type, effect, faction }) {
  const normalizedType = type.toLowerCase();
  const normalizedEffect = effect.toLowerCase();
  if (normalizedType === "leader" || row.toLowerCase() === "leader") {
    return `an original commanding dark-fantasy leader inspired by the card title "${title}", shown as a distinct non-franchise character with no recognizable emblem`;
  }
  if (normalizedType === "special" && normalizedEffect.includes("weather")) {
    return `an original magical weather scene for "${title}", with the weather itself as the main subject and no characters in the foreground`;
  }
  if (normalizedEffect === "commanders_horn") {
    return `an ornate battle horn and torn command banner for "${title}", dramatic but original, no readable symbols`;
  }
  if (normalizedEffect === "decoy") {
    return `a rugged battlefield decoy dummy for "${title}", cloak, straw and worn leather, no living character`;
  }
  if (normalizedEffect.startsWith("scorch")) {
    return `a scorched battlefield omen for "${title}", burning earth and shattered weapons, no gore`;
  }
  return `an original dark-fantasy ${faction || "neutral"} unit or hero inspired by the card title "${title}", distinct from any official character likeness`;
}

function defaultScene(row, effect) {
  const normalizedRow = row.toLowerCase();
  const normalizedEffect = effect.toLowerCase();
  if (normalizedEffect.includes("weather")) {
    return "wide atmospheric battlefield sky, strong weather mood, simple low-detail background so UI icons can sit on top.";
  }
  if (normalizedRow === "siege") {
    return "muddy siege line at dusk, distant palisade and smoke, simple low-detail background so UI icons can sit on top.";
  }
  if (normalizedRow === "ranged") {
    return "misty forest edge at dusk, cold blue-green fog, faint amber torchlight, simple low-detail background so UI icons can sit on top.";
  }
  if (normalizedRow === "leader") {
    return "war council tent or ruined keep at dusk, restrained banners without readable symbols, simple low-detail background so UI icons can sit on top.";
  }
  return "misty pine forest at dusk, cold blue-green fog, faint warm amber firelight from one side, simple low-detail background so UI icons can sit on top.";
}

async function loadCatalogCard(filePath, wantedCardId) {
  try {
    const text = await fs.readFile(filePath, "utf8");
    const [headerLine, ...lines] = text.split(/\r?\n/).filter(Boolean);
    const headers = parseCsvLine(headerLine);
    for (const line of lines) {
      const values = parseCsvLine(line);
      const row = Object.fromEntries(headers.map((header, index) => [header, values[index] || ""]));
      if (row.card_id === wantedCardId) {
        return row;
      }
    }
  } catch (error) {
    if (error?.code !== "ENOENT") {
      throw error;
    }
  }
  return null;
}

function parseCsvLine(line) {
  const values = [];
  let current = "";
  let quoted = false;
  for (let index = 0; index < line.length; index += 1) {
    const char = line[index];
    const next = line[index + 1];
    if (char === '"' && quoted && next === '"') {
      current += '"';
      index += 1;
    } else if (char === '"') {
      quoted = !quoted;
    } else if (char === "," && !quoted) {
      values.push(current);
      current = "";
    } else {
      current += char;
    }
  }
  values.push(current);
  return values;
}

function readableIdentifier(value) {
  return value
    .replace(/^gwent_/, "")
    .split("_")
    .filter(Boolean)
    .map((word) => word[0].toUpperCase() + word.slice(1))
    .join(" ");
}

function envFlag(name) {
  const value = envValue(name).toLowerCase();
  return value === "1" || value === "true" || value === "yes";
}

function envValue(name) {
  return (process.env[name] || externalEnv[name] || "").trim();
}

async function loadEnvFile(filePath) {
  const text = await fs.readFile(filePath, "utf8");
  const result = {};
  for (const line of text.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const match = trimmed.match(/^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$/);
    if (!match) continue;
    let value = match[2].trim();
    if (
      (value.startsWith("\"") && value.endsWith("\"")) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    result[match[1]] = value;
  }
  return result;
}
