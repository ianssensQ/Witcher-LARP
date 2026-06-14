import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const { PNG } = require("../prototypes/stage2b-v2/node_modules/pngjs");

const TARGET_WIDTH = 1170;
const TARGET_HEIGHT = 1266;
const TARGET_RATIO = TARGET_WIDTH / TARGET_HEIGHT;
const RATIO_TOLERANCE = 0.002;

function usage() {
  console.log(
    [
      "Usage:",
      "  node scripts/pve_imagegen_exact.mjs inspect <png>",
      "  node scripts/pve_imagegen_exact.mjs normalize <input.png> <output.png>",
      "  node scripts/pve_imagegen_exact.mjs sheet <output.png> <input.png> [input.png ...]",
      "",
      "normalize resamples to 1170x1266 only when the input ratio already matches.",
      "It never crops or pads.",
    ].join("\n"),
  );
}

function readPng(filePath) {
  return PNG.sync.read(fs.readFileSync(filePath));
}

function writePng(filePath, png) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, PNG.sync.write(png));
}

function inspect(filePath) {
  const png = readPng(filePath);
  return {
    path: filePath,
    width: png.width,
    height: png.height,
    ratio: png.width / png.height,
    exact: png.width === TARGET_WIDTH && png.height === TARGET_HEIGHT,
  };
}

function assertCompatibleRatio(png, filePath) {
  const ratio = png.width / png.height;
  const delta = Math.abs(ratio - TARGET_RATIO);
  if (delta > RATIO_TOLERANCE) {
    throw new Error(
      `Refusing to normalize ${filePath}: ratio ${ratio.toFixed(6)} is not target ${TARGET_RATIO.toFixed(6)}. Regenerate with a 195:211 / 1170x1266 portrait canvas prompt.`,
    );
  }
}

function resizeBilinear(source, width, height) {
  const target = new PNG({ width, height });
  const xScale = source.width / width;
  const yScale = source.height / height;

  for (let y = 0; y < height; y += 1) {
    const srcY = (y + 0.5) * yScale - 0.5;
    const y0 = Math.max(0, Math.floor(srcY));
    const y1 = Math.min(source.height - 1, y0 + 1);
    const yWeight = srcY - y0;

    for (let x = 0; x < width; x += 1) {
      const srcX = (x + 0.5) * xScale - 0.5;
      const x0 = Math.max(0, Math.floor(srcX));
      const x1 = Math.min(source.width - 1, x0 + 1);
      const xWeight = srcX - x0;
      const outIndex = (y * width + x) * 4;

      const i00 = (y0 * source.width + x0) * 4;
      const i10 = (y0 * source.width + x1) * 4;
      const i01 = (y1 * source.width + x0) * 4;
      const i11 = (y1 * source.width + x1) * 4;

      for (let channel = 0; channel < 4; channel += 1) {
        const top =
          source.data[i00 + channel] * (1 - xWeight) +
          source.data[i10 + channel] * xWeight;
        const bottom =
          source.data[i01 + channel] * (1 - xWeight) +
          source.data[i11 + channel] * xWeight;
        target.data[outIndex + channel] = Math.round(top * (1 - yWeight) + bottom * yWeight);
      }
    }
  }

  return target;
}

function normalize(inputPath, outputPath) {
  const source = readPng(inputPath);
  assertCompatibleRatio(source, inputPath);

  const finalPng =
    source.width === TARGET_WIDTH && source.height === TARGET_HEIGHT
      ? source
      : resizeBilinear(source, TARGET_WIDTH, TARGET_HEIGHT);

  writePng(outputPath, finalPng);
  const result = inspect(outputPath);
  if (!result.exact) {
    throw new Error(`Pixel gate failed for ${outputPath}: ${result.width}x${result.height}`);
  }
  return result;
}

function makeSheet(outputPath, inputPaths) {
  if (inputPaths.length === 0) {
    throw new Error("sheet requires at least one input image");
  }

  const images = inputPaths.map((inputPath) => ({ inputPath, png: readPng(inputPath) }));
  for (const image of images) {
    if (image.png.width !== TARGET_WIDTH || image.png.height !== TARGET_HEIGHT) {
      throw new Error(
        `Contact sheet input is not ${TARGET_WIDTH}x${TARGET_HEIGHT}: ${image.inputPath} is ${image.png.width}x${image.png.height}`,
      );
    }
  }

  const thumbWidth = 234;
  const thumbHeight = 253;
  const gap = 16;
  const columns = Math.min(3, images.length);
  const rows = Math.ceil(images.length / columns);
  const width = columns * thumbWidth + (columns + 1) * gap;
  const height = rows * thumbHeight + (rows + 1) * gap;
  const sheet = new PNG({ width, height });
  sheet.data.fill(24);
  for (let i = 3; i < sheet.data.length; i += 4) sheet.data[i] = 255;

  images.forEach(({ png }, index) => {
    const col = index % columns;
    const row = Math.floor(index / columns);
    const offsetX = gap + col * (thumbWidth + gap);
    const offsetY = gap + row * (thumbHeight + gap);
    const thumb = resizeBilinear(png, thumbWidth, thumbHeight);

    for (let y = 0; y < thumbHeight; y += 1) {
      for (let x = 0; x < thumbWidth; x += 1) {
        const sourceIndex = (y * thumbWidth + x) * 4;
        const targetIndex = ((offsetY + y) * width + offsetX + x) * 4;
        sheet.data[targetIndex] = thumb.data[sourceIndex];
        sheet.data[targetIndex + 1] = thumb.data[sourceIndex + 1];
        sheet.data[targetIndex + 2] = thumb.data[sourceIndex + 2];
        sheet.data[targetIndex + 3] = 255;
      }
    }
  });

  writePng(outputPath, sheet);
  return inspect(outputPath);
}

const [command, ...args] = process.argv.slice(2);

try {
  if (command === "inspect" && args.length === 1) {
    console.log(JSON.stringify(inspect(args[0]), null, 2));
  } else if (command === "normalize" && args.length === 2) {
    console.log(JSON.stringify(normalize(args[0], args[1]), null, 2));
  } else if (command === "sheet" && args.length >= 2) {
    const [outputPath, ...inputPaths] = args;
    console.log(JSON.stringify(makeSheet(outputPath, inputPaths), null, 2));
  } else {
    usage();
    process.exitCode = 2;
  }
} catch (error) {
  console.error(error.message);
  process.exitCode = 1;
}
