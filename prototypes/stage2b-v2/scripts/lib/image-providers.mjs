import fs from "node:fs/promises";
import path from "node:path";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { fileURLToPath } from "node:url";
import { PNG } from "pngjs";
import { requireEnv } from "./env.mjs";

const execFileAsync = promisify(execFile);
const providerDir = path.dirname(fileURLToPath(import.meta.url));
const wicConverterPath = path.join(providerDir, "convert-wic.ps1");

export async function generateOpenRouterImage({
  env,
  model = "openai/gpt-5.4-image-2",
  prompt,
  outputPath,
  aspectRatio = "16:9",
  imageSize = "2K",
}) {
  const apiKey = requireEnv(env, "OPENROUTER_API_KEY");
  const baseUrl = requireEnv(env, "OPENROUTER_BASE_URL").replace(/\/$/, "");
  const referer = env.values.OPENROUTER_HTTP_REFERER || "http://127.0.0.1:5178";
  const title = env.values.OPENROUTER_APP_TITLE || "Witcher LARP UI asset pipeline";

  const data =
    process.env.OPENROUTER_TRANSPORT === "fetch"
      ? await generateOpenRouterImageWithFetch({
          apiKey,
          baseUrl,
          referer,
          title,
          model,
          prompt,
          aspectRatio,
          imageSize,
        })
      : await generateOpenRouterImageWithCurl({
          apiKey,
          baseUrl,
          referer,
          title,
          model,
          prompt,
          aspectRatio,
          imageSize,
          responsePath: `${outputPath}.openrouter-response.json`,
        });

  const message = data.choices?.[0]?.message;
  const image = message?.images?.[0];
  const dataUrl = image?.image_url?.url || image?.imageUrl?.url;

  if (!dataUrl) {
    throw new Error(`OpenRouter response did not include an image for ${outputPath}`);
  }

  if (/^https?:\/\//i.test(dataUrl)) {
    await downloadImage(dataUrl, outputPath);
  } else {
    await saveDataUrl(dataUrl, outputPath);
  }
  return { provider: "openrouter", model, outputPath };
}

async function generateOpenRouterImageWithFetch({
  apiKey,
  baseUrl,
  referer,
  title,
  model,
  prompt,
  aspectRatio,
  imageSize,
}) {
  const response = await fetchWithRetry(
    () =>
      fetch(`${baseUrl}/chat/completions`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${apiKey}`,
          "Content-Type": "application/json",
          "HTTP-Referer": referer,
          "X-Title": title,
        },
        body: JSON.stringify({
          model,
          messages: [{ role: "user", content: prompt }],
          modalities: ["image", "text"],
          image_config: {
            aspect_ratio: aspectRatio,
            image_size: imageSize,
          },
          stream: false,
        }),
        signal: AbortSignal.timeout(180_000),
      }),
    "OpenRouter",
    1,
  );

  return parseProviderResponse(response, "OpenRouter");
}

async function generateOpenRouterImageWithCurl({
  apiKey,
  baseUrl,
  referer,
  title,
  model,
  prompt,
  aspectRatio,
  imageSize,
  responsePath,
}) {
  await fs.mkdir(path.dirname(responsePath), { recursive: true });

  const bodyPath = `${responsePath}.request.json`;
  await fs.writeFile(
    bodyPath,
    `${JSON.stringify({
      model,
      messages: [{ role: "user", content: prompt }],
      modalities: ["image", "text"],
      image_config: {
        aspect_ratio: aspectRatio,
        image_size: imageSize,
      },
      stream: false,
    })}\n`,
  );

  const args = [
    "-sS",
    "--connect-timeout",
    "30",
    "--max-time",
    "240",
    "-X",
    "POST",
    `${baseUrl}/chat/completions`,
    "-H",
    `Authorization: Bearer ${apiKey}`,
    "-H",
    "Content-Type: application/json",
    "-H",
    `HTTP-Referer: ${referer}`,
    "-H",
    `X-Title: ${title}`,
    "--data-binary",
    `@${bodyPath}`,
    "-o",
    responsePath,
    "-w",
    "%{http_code}",
  ];

  let stdout = "";
  try {
    const result = await execFileAsync("curl.exe", args, {
      windowsHide: true,
      maxBuffer: 1024 * 1024,
    });
    stdout = result.stdout.trim();
  } catch (error) {
    stdout = (error.stdout || "").trim();
    const details = await readOptionalText(responsePath);
    throw new Error(
      `OpenRouter curl request failed: ${error.message}. Response: ${details.slice(0, 1200)}`,
    );
  } finally {
    await fs.unlink(bodyPath).catch(() => {});
  }

  const status = Number(stdout.slice(-3));
  const text = await fs.readFile(responsePath, "utf8");
  let data;

  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    throw new Error(`OpenRouter returned non-JSON response: ${text.slice(0, 500)}`);
  }

  if (!Number.isFinite(status) || status < 200 || status >= 300) {
    throw new Error(`OpenRouter request failed ${status || "unknown"}: ${text.slice(0, 1200)}`);
  }

  return data;
}

export async function generateRecraftImage({
  env,
  prompt,
  outputPath,
  model = "recraftv4_1_pro",
  size = "1024x1024",
  style,
  negativePrompt,
  endpoint = "/images/generations",
  removeBackground = false,
  trimTransparent = false,
}) {
  const apiKey = requireEnv(env, "RECRAFT_API_KEY");

  const body = {
    prompt,
    n: 1,
    model,
    size,
    response_format: "b64_json",
  };

  if (style) body.style = style;
  if (negativePrompt) body.negative_prompt = negativePrompt;

  const rawOutputPath = removeBackground ? `${outputPath}.raw.png` : outputPath;
  const response = await fetchWithRetry(
    () =>
      fetch(`https://external.api.recraft.ai/v1${endpoint}`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${apiKey}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify(body),
        signal: AbortSignal.timeout(180_000),
      }),
    "Recraft",
    1,
  );

  const data = await parseProviderResponse(response, "Recraft");
  const first = data.data?.[0] || data.image;

  if (first?.b64_json) {
    await saveBase64(first.b64_json, rawOutputPath);
  } else if (first?.url) {
    await downloadImage(first.url, rawOutputPath);
  } else {
    throw new Error(`Recraft response did not include an image for ${outputPath}`);
  }

  if (removeBackground) {
    await removeRecraftBackground({ env, inputPath: rawOutputPath, outputPath });
    await fs.unlink(rawOutputPath).catch(() => {});
  }

  if (trimTransparent) {
    await trimTransparentPng(outputPath, outputPath);
  }

  return { provider: "recraft", model, outputPath };
}

export async function removeRecraftBackground({ env, inputPath, outputPath }) {
  const apiKey = requireEnv(env, "RECRAFT_API_KEY");
  const imageBuffer = await fs.readFile(inputPath);

  const response = await fetchWithRetry(
    () => {
      const form = new FormData();
      form.append("file", new Blob([imageBuffer], { type: "image/png" }), path.basename(inputPath));
      form.append("response_format", "b64_json");

      return fetch("https://external.api.recraft.ai/v1/images/removeBackground", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${apiKey}`,
        },
        body: form,
        signal: AbortSignal.timeout(180_000),
      });
    },
    "Recraft removeBackground",
    1,
  );

  const data = await parseProviderResponse(response, "Recraft removeBackground");
  const image = data.image || data.data?.[0];

  if (image?.b64_json) {
    await saveBase64(image.b64_json, outputPath);
  } else if (image?.url) {
    await downloadImage(image.url, outputPath);
  } else {
    throw new Error(`Recraft removeBackground response did not include an image for ${outputPath}`);
  }

  return { provider: "recraft", operation: "removeBackground", outputPath };
}

export async function trimTransparentPng(inputPath, outputPath, marginRatio = 0.04) {
  await ensurePngFile(inputPath);
  const buffer = await fs.readFile(inputPath);
  const png = PNG.sync.read(buffer);
  let minX = png.width;
  let minY = png.height;
  let maxX = -1;
  let maxY = -1;

  for (let y = 0; y < png.height; y += 1) {
    for (let x = 0; x < png.width; x += 1) {
      const alpha = png.data[(png.width * y + x) * 4 + 3];
      if (alpha > 8) {
        minX = Math.min(minX, x);
        minY = Math.min(minY, y);
        maxX = Math.max(maxX, x);
        maxY = Math.max(maxY, y);
      }
    }
  }

  if (maxX < 0 || maxY < 0) return;

  const margin = Math.round(Math.max(maxX - minX, maxY - minY) * marginRatio);
  minX = Math.max(0, minX - margin);
  minY = Math.max(0, minY - margin);
  maxX = Math.min(png.width - 1, maxX + margin);
  maxY = Math.min(png.height - 1, maxY + margin);

  const width = maxX - minX + 1;
  const height = maxY - minY + 1;
  const cropped = new PNG({ width, height });

  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      const source = ((y + minY) * png.width + (x + minX)) * 4;
      const target = (y * width + x) * 4;
      png.data.copy(cropped.data, target, source, source + 4);
    }
  }

  await fs.writeFile(outputPath, PNG.sync.write(cropped));
}

export async function removeChromaKeyPng(inputPath, outputPath, options = {}) {
  await ensurePngFile(inputPath);
  const {
    key = [0, 255, 0],
    hardDistance = 92,
    softDistance = 150,
    spill = true,
  } = options;
  const buffer = await fs.readFile(inputPath);
  const png = PNG.sync.read(buffer);

  for (let y = 0; y < png.height; y += 1) {
    for (let x = 0; x < png.width; x += 1) {
      const index = (png.width * y + x) * 4;
      const r = png.data[index];
      const g = png.data[index + 1];
      const b = png.data[index + 2];
      const distance = Math.sqrt(
        (r - key[0]) ** 2 + (g - key[1]) ** 2 + (b - key[2]) ** 2,
      );

      const greenDominant = g > 120 && g > r * 1.35 && g > b * 1.35;
      if (distance < hardDistance || greenDominant) {
        png.data[index] = 0;
        png.data[index + 1] = 0;
        png.data[index + 2] = 0;
        png.data[index + 3] = 0;
        continue;
      }

      if (distance < softDistance) {
        const alphaFactor = Math.min(1, (distance - hardDistance) / (softDistance - hardDistance));
        png.data[index + 3] = Math.round(png.data[index + 3] * alphaFactor);
        if (png.data[index + 3] < 4) {
          png.data[index] = 0;
          png.data[index + 1] = 0;
          png.data[index + 2] = 0;
          png.data[index + 3] = 0;
        }
      }

      if (spill && g > r && g > b) {
        png.data[index + 1] = Math.round(Math.min(g, (r + b) * 0.62));
      }
    }
  }

  await fs.writeFile(outputPath, PNG.sync.write(png));
}

export async function ensurePngFile(inputPath) {
  const header = await readHeader(inputPath);
  if (isPng(header)) return;

  const tmpPath = `${inputPath}.converted.png`;
  await execFileAsync("powershell.exe", [
    "-NoProfile",
    "-ExecutionPolicy",
    "Bypass",
    "-File",
    wicConverterPath,
    "-InputFile",
    inputPath,
    "-OutputFile",
    tmpPath,
  ]);
  await fs.rename(tmpPath, inputPath);
}

async function readHeader(inputPath) {
  const handle = await fs.open(inputPath, "r");
  try {
    const buffer = Buffer.alloc(16);
    await handle.read(buffer, 0, buffer.length, 0);
    return buffer;
  } finally {
    await handle.close();
  }
}

function isPng(header) {
  return (
    header[0] === 0x89 &&
    header[1] === 0x50 &&
    header[2] === 0x4e &&
    header[3] === 0x47 &&
    header[4] === 0x0d &&
    header[5] === 0x0a &&
    header[6] === 0x1a &&
    header[7] === 0x0a
  );
}

function isWebp(header) {
  return (
    header.toString("ascii", 0, 4) === "RIFF" &&
    header.toString("ascii", 8, 12) === "WEBP"
  );
}

export async function generateIdeogramImage({
  env,
  prompt,
  outputPath,
  endpoint = "/v1/ideogram-v3/generate-transparent",
  aspectRatio = "1x1",
  resolution,
  renderingSpeed = "QUALITY",
  styleType,
  negativePrompt,
  textField = "prompt",
}) {
  const apiKey = requireEnv(env, "IDEOGRAM_API_KEY");

  const data =
    process.env.IDEOGRAM_TRANSPORT === "fetch"
      ? await generateIdeogramImageWithFetch({
          apiKey,
          prompt,
          endpoint,
          aspectRatio,
          resolution,
          renderingSpeed,
          styleType,
          negativePrompt,
          textField,
        })
      : await generateIdeogramImageWithCurl({
          apiKey,
          prompt,
          endpoint,
          aspectRatio,
          resolution,
          renderingSpeed,
          styleType,
          negativePrompt,
          textField,
          responsePath: `${outputPath}.ideogram-response.json`,
        });

  const url = data.data?.[0]?.url;

  if (!url) {
    throw new Error(`Ideogram response did not include an image URL for ${outputPath}`);
  }

  await downloadImage(url, outputPath);
  return { provider: "ideogram", endpoint, outputPath };
}

export async function editIdeogramImage({
  env,
  inputPath,
  prompt,
  outputPath,
  endpoint = "/v1/edit",
  aspectRatio = "16x9",
  resolution,
  magicPrompt = "OFF",
  transparentBackground = true,
}) {
  const apiKey = requireEnv(env, "IDEOGRAM_API_KEY");
  const responsePath = `${outputPath}.ideogram-edit-response.json`;

  await fs.mkdir(path.dirname(responsePath), { recursive: true });

  const args = [
    "-sS",
    "--connect-timeout",
    "30",
    "--max-time",
    "240",
    "-X",
    "POST",
    `https://api.ideogram.ai${endpoint}`,
    "-H",
    `Api-Key: ${apiKey}`,
    "-F",
    `images=@${inputPath}`,
    "-F",
    `prompt=${prompt}`,
    "-F",
    "num_images=1",
    "-F",
    `magic_prompt=${magicPrompt}`,
    "-F",
    `transparent_background=${transparentBackground ? "true" : "false"}`,
    "-o",
    responsePath,
    "-w",
    "%{http_code}",
  ];

  if (aspectRatio) args.splice(-4, 0, "-F", `aspect_ratio=${aspectRatio}`);
  if (resolution) args.splice(-4, 0, "-F", `resolution=${resolution}`);

  let stdout = "";
  try {
    const result = await execFileAsync("curl.exe", args, {
      windowsHide: true,
      maxBuffer: 1024 * 1024,
    });
    stdout = result.stdout.trim();
  } catch (error) {
    stdout = (error.stdout || "").trim();
    const details = await readOptionalText(responsePath);
    throw new Error(
      `Ideogram edit request failed: ${error.message}. Response: ${details.slice(0, 1200)}`,
    );
  }

  const status = Number(stdout.slice(-3));
  const text = await fs.readFile(responsePath, "utf8");
  let data;

  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    throw new Error(`Ideogram edit returned non-JSON response: ${text.slice(0, 500)}`);
  }

  if (!Number.isFinite(status) || status < 200 || status >= 300) {
    throw new Error(`Ideogram edit failed ${status || "unknown"}: ${text.slice(0, 1200)}`);
  }

  const url = data.data?.[0]?.url;
  if (!url) {
    throw new Error(`Ideogram edit response did not include an image URL for ${outputPath}`);
  }

  await downloadImage(url, outputPath);
  return { provider: "ideogram-edit", endpoint, outputPath };
}

async function generateIdeogramImageWithFetch({
  apiKey,
  prompt,
  endpoint,
  aspectRatio,
  resolution,
  renderingSpeed,
  styleType,
  negativePrompt,
  textField,
}) {
  const response = await fetchWithRetry(
    () => {
      const form = new FormData();

      form.append(textField, prompt);
      form.append("rendering_speed", renderingSpeed);
      form.append("num_images", "1");

      if (aspectRatio) form.append("aspect_ratio", aspectRatio);
      if (resolution) form.append("resolution", resolution);
      if (styleType) form.append("style_type", styleType);
      if (negativePrompt) form.append("negative_prompt", negativePrompt);

      return fetch(`https://api.ideogram.ai${endpoint}`, {
        method: "POST",
        headers: {
          "Api-Key": apiKey,
        },
        body: form,
        signal: AbortSignal.timeout(180_000),
      });
    },
    "Ideogram",
    1,
  );

  return parseProviderResponse(response, "Ideogram");
}

async function generateIdeogramImageWithCurl({
  apiKey,
  prompt,
  endpoint,
  aspectRatio,
  resolution,
  renderingSpeed,
  styleType,
  negativePrompt,
  textField,
  responsePath,
}) {
  await fs.mkdir(path.dirname(responsePath), { recursive: true });

  const args = [
    "-sS",
    "--connect-timeout",
    "30",
    "--max-time",
    "240",
    "-X",
    "POST",
    `https://api.ideogram.ai${endpoint}`,
    "-H",
    `Api-Key: ${apiKey}`,
    "-F",
    `${textField}=${prompt}`,
    "-F",
    `rendering_speed=${renderingSpeed}`,
    "-F",
    "num_images=1",
    "-o",
    responsePath,
    "-w",
    "%{http_code}",
  ];

  if (aspectRatio) args.splice(-4, 0, "-F", `aspect_ratio=${aspectRatio}`);
  if (resolution) args.splice(-4, 0, "-F", `resolution=${resolution}`);
  if (styleType) args.splice(-4, 0, "-F", `style_type=${styleType}`);
  if (negativePrompt) args.splice(-4, 0, "-F", `negative_prompt=${negativePrompt}`);

  let stdout = "";
  try {
    const result = await execFileAsync("curl.exe", args, {
      windowsHide: true,
      maxBuffer: 1024 * 1024,
    });
    stdout = result.stdout.trim();
  } catch (error) {
    stdout = (error.stdout || "").trim();
    const details = await readOptionalText(responsePath);
    throw new Error(
      `Ideogram curl request failed: ${error.message}. Response: ${details.slice(0, 1200)}`,
    );
  }

  const status = Number(stdout.slice(-3));
  const text = await fs.readFile(responsePath, "utf8");
  let data;

  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    throw new Error(`Ideogram returned non-JSON response: ${text.slice(0, 500)}`);
  }

  if (!Number.isFinite(status) || status < 200 || status >= 300) {
    throw new Error(`Ideogram request failed ${status || "unknown"}: ${text.slice(0, 1200)}`);
  }

  return data;
}

export async function downloadImage(url, outputPath) {
  if (process.platform === "win32" && process.env.IMAGE_DOWNLOAD_TRANSPORT !== "fetch") {
    await downloadImageWithCurl(url, outputPath);
    return;
  }

  const response = await fetchWithRetry(
    () => fetch(url, { signal: AbortSignal.timeout(180_000) }),
    "Image download",
  );
  if (!response.ok) {
    throw new Error(`Image download failed ${response.status}: ${url}`);
  }

  const buffer = Buffer.from(await response.arrayBuffer());
  await fs.mkdir(path.dirname(outputPath), { recursive: true });
  await fs.writeFile(outputPath, buffer);
}

async function downloadImageWithCurl(url, outputPath) {
  await fs.mkdir(path.dirname(outputPath), { recursive: true });

  await execFileAsync(
    "curl.exe",
    [
      "-sS",
      "-L",
      "--connect-timeout",
      "30",
      "--max-time",
      "180",
      "--retry",
      "3",
      "--retry-delay",
      "2",
      "-o",
      outputPath,
      url,
    ],
    {
      windowsHide: true,
      maxBuffer: 1024 * 1024,
    },
  );
}

export async function saveDataUrl(dataUrl, outputPath) {
  const [, payload] = dataUrl.split(",");
  if (!payload) {
    throw new Error(`Invalid image data URL for ${outputPath}`);
  }
  await saveBase64(payload, outputPath);
}

export async function saveBase64(payload, outputPath) {
  await fs.mkdir(path.dirname(outputPath), { recursive: true });
  await fs.writeFile(outputPath, Buffer.from(payload, "base64"));
}

async function parseProviderResponse(response, provider) {
  const text = await response.text();
  let data;

  try {
    data = text ? JSON.parse(text) : {};
  } catch (error) {
    throw new Error(`${provider} returned non-JSON response: ${text.slice(0, 500)}`);
  }

  if (!response.ok) {
    const details = JSON.stringify(data, null, 2).slice(0, 1200);
    throw new Error(`${provider} request failed ${response.status}: ${details}`);
  }

  return data;
}

async function fetchWithRetry(factory, label, attempts = 3) {
  let lastError;

  for (let attempt = 1; attempt <= attempts; attempt += 1) {
    try {
      const response = await factory();
      if (response.status >= 500 && attempt < attempts) {
        lastError = new Error(`${label} returned ${response.status}`);
        await wait(attempt * 1500);
        continue;
      }
      return response;
    } catch (error) {
      lastError = error;
      if (attempt >= attempts) break;
      console.warn(`${label} network error, retry ${attempt + 1}/${attempts}: ${error.message}`);
      await wait(attempt * 1500);
    }
  }

  throw lastError;
}

function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function readOptionalText(targetPath) {
  try {
    return await fs.readFile(targetPath, "utf8");
  } catch {
    return "";
  }
}
