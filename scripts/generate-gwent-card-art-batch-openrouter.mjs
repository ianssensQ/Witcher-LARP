import fs from "node:fs/promises";
import path from "node:path";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(__dirname, "..");
const singleGenerator = path.join(repoRoot, "scripts", "generate-gwent-card-art-openrouter.mjs");
const catalogPath = path.resolve(repoRoot, envValue("GWENT_CARD_CATALOG") || "data/seed/gwent_cards.csv");
const artifactDir = path.join(repoRoot, "artifacts", "openrouter");
const reportPath = path.resolve(
  repoRoot,
  envValue("GWENT_BATCH_REPORT") || path.join("artifacts", "openrouter", `gwent-card-art-batch-${timestamp()}.json`),
);

const concurrency = clampInt(envInt("GWENT_CONCURRENCY", 4), 1, 12);
const retries = clampInt(envInt("GWENT_RETRIES", 2), 0, 8);
const retryBaseMs = clampInt(envInt("GWENT_RETRY_BASE_MS", 6000), 250, 120000);
const skipExisting = !envFlag("GWENT_FORCE") && envFlagDefault("GWENT_SKIP_EXISTING", true);
const batchDryRun = envFlag("GWENT_BATCH_DRY_RUN");
const offset = Math.max(0, envInt("GWENT_OFFSET", 0));
const limit = envInt("GWENT_LIMIT", 0);
const requestedIds = await requestedCardIds();
const catalog = await loadCatalog(catalogPath);
const cards = selectCards(catalog, requestedIds, offset, limit);

if (cards.length === 0) {
  throw new Error("No cards selected for batch generation.");
}

await fs.mkdir(artifactDir, { recursive: true });

const startedAt = new Date();
const jobs = cards.map((card, index) => ({
  index,
  cardId: card.card_id,
  title: card.display_name || readableIdentifier(card.card_id),
  assetName: `gwent_card_art_${card.card_id}`,
}));
const results = [];
let cursor = 0;

console.log(
  [
    `batch cards=${jobs.length}`,
    `concurrency=${concurrency}`,
    `retries=${retries}`,
    `skipExisting=${skipExisting}`,
    `dryRun=${batchDryRun || envFlag("GWENT_DRY_RUN")}`,
    `report=${reportPath}`,
  ].join(" "),
);

if (jobs.length > 1 && envValue("GWENT_ASSET_NAME")) {
  console.warn("Ignoring GWENT_ASSET_NAME for multi-card batch; asset names are derived from each card_id.");
}

await Promise.all(Array.from({ length: concurrency }, (_, index) => worker(index + 1)));
results.sort((left, right) => left.index - right.index);

const finishedAt = new Date();
const report = {
  status: results.some((result) => result.status === "failed") ? "failed" : "completed",
  started_at: startedAt.toISOString(),
  finished_at: finishedAt.toISOString(),
  duration_seconds: Math.round((finishedAt.getTime() - startedAt.getTime()) / 1000),
  config: {
    catalog_path: catalogPath,
    concurrency,
    retries,
    retry_base_ms: retryBaseMs,
    skip_existing: skipExisting,
    batch_dry_run: batchDryRun,
    child_dry_run: envFlag("GWENT_DRY_RUN"),
    offset,
    limit,
  },
  counts: countStatuses(results),
  results,
};

await fs.mkdir(path.dirname(reportPath), { recursive: true });
await fs.writeFile(reportPath, `${JSON.stringify(report, null, 2)}\n`);
console.log(`report ${reportPath}`);
console.log(`done ${JSON.stringify(report.counts)}`);

if (report.status === "failed") {
  process.exitCode = 1;
}

async function worker(workerId) {
  for (;;) {
    const job = jobs[cursor];
    cursor += 1;
    if (!job) return;
    const prefix = `[${job.index + 1}/${jobs.length} w${workerId}]`;
    console.log(`${prefix} ${job.cardId} ${job.title}`);
    const result = await runJob(job);
    results.push(result);
    console.log(`${prefix} ${job.cardId} ${result.status}${result.attempts ? ` attempts=${result.attempts}` : ""}`);
  }
}

async function runJob(job) {
  const imageSetDir = path.join(repoRoot, "ios", "Resources", "Assets.xcassets", `${job.assetName}.imageset`);
  const outputPath = path.join(imageSetDir, `${job.assetName}.png`);
  const promptPath = path.join(artifactDir, `${job.assetName}.prompt.txt`);
  const exists = await fileExists(outputPath);

  if (skipExisting && exists) {
    return {
      index: job.index,
      card_id: job.cardId,
      title: job.title,
      status: "skipped_existing",
      output_path: outputPath,
    };
  }

  if (batchDryRun) {
    return {
      index: job.index,
      card_id: job.cardId,
      title: job.title,
      status: "planned",
      output_path: outputPath,
      prompt_path: promptPath,
    };
  }

  let lastFailure = null;
  let attemptsUsed = 0;
  for (let attempt = 1; attempt <= retries + 1; attempt += 1) {
    attemptsUsed = attempt;
    const started = Date.now();
    const child = await runSingleGenerator(job.cardId, jobs.length === 1);
    const durationMs = Date.now() - started;
    if (child.code === 0) {
      return {
        index: job.index,
        card_id: job.cardId,
        title: job.title,
        status: envFlag("GWENT_DRY_RUN") ? "prompted" : "generated",
        attempts: attempt,
        duration_ms: durationMs,
        output_path: outputPath,
        prompt_path: promptPath,
        stdout_tail: tail(child.stdout),
      };
    }

    lastFailure = {
      code: child.code,
      signal: child.signal,
      stdout_tail: tail(child.stdout),
      stderr_tail: tail(child.stderr),
    };
    if (attempt <= retries && shouldRetry(lastFailure)) {
      await sleep(retryDelayMs(attempt));
      continue;
    }
    break;
  }

  return {
    index: job.index,
    card_id: job.cardId,
    title: job.title,
    status: "failed",
    attempts: attemptsUsed,
    output_path: outputPath,
    prompt_path: promptPath,
    error: lastFailure,
  };
}

function runSingleGenerator(cardId, allowCustomAssetName) {
  return new Promise((resolve) => {
    const childEnv = {
      ...process.env,
      GWENT_CARD_ID: cardId,
    };
    delete childEnv.GWENT_CARD_IDS;
    delete childEnv.GWENT_CARD_IDS_FILE;
    delete childEnv.GWENT_CARD_FILTER;
    delete childEnv.GWENT_BATCH_DRY_RUN;
    delete childEnv.GWENT_BATCH_REPORT;
    delete childEnv.GWENT_CONCURRENCY;
    delete childEnv.GWENT_LIMIT;
    delete childEnv.GWENT_OFFSET;
    delete childEnv.GWENT_RETRIES;
    delete childEnv.GWENT_RETRY_BASE_MS;
    delete childEnv.GWENT_SKIP_EXISTING;
    delete childEnv.GWENT_FORCE;
    if (!allowCustomAssetName) {
      delete childEnv.GWENT_ASSET_NAME;
    }

    const child = spawn(process.execPath, [singleGenerator], {
      cwd: repoRoot,
      env: childEnv,
      stdio: ["ignore", "pipe", "pipe"],
    });
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (chunk) => {
      stdout += chunk.toString();
    });
    child.stderr.on("data", (chunk) => {
      stderr += chunk.toString();
    });
    child.on("close", (code, signal) => {
      resolve({ code, signal, stdout, stderr });
    });
  });
}

async function requestedCardIds() {
  const inline = envValue("GWENT_CARD_IDS");
  const filePath = envValue("GWENT_CARD_IDS_FILE");
  const ids = [];
  if (inline) {
    ids.push(...splitIds(inline));
  }
  if (filePath) {
    const text = await fs.readFile(path.resolve(repoRoot, filePath), "utf8");
    ids.push(...splitIds(text));
  }
  return ids;
}

function selectCards(catalog, ids, sliceOffset, sliceLimit) {
  const byId = new Map(catalog.map((row) => [row.card_id, row]));
  const selected = ids.length > 0
    ? ids.map((id) => byId.get(id) || { card_id: id }).filter((row) => validateCardId(row.card_id))
    : catalog.filter((row) => validateCardId(row.card_id));
  const filter = envValue("GWENT_CARD_FILTER");
  const filtered = filter
    ? selected.filter((row) => new RegExp(filter).test(row.card_id))
    : selected;
  const start = Math.min(sliceOffset, filtered.length);
  const end = sliceLimit > 0 ? Math.min(start + sliceLimit, filtered.length) : filtered.length;
  return filtered.slice(start, end);
}

async function loadCatalog(filePath) {
  const text = await fs.readFile(filePath, "utf8");
  const [headerLine, ...lines] = text.split(/\r?\n/).filter(Boolean);
  const headers = parseCsvLine(headerLine);
  return lines.map((line) => {
    const values = parseCsvLine(line);
    return Object.fromEntries(headers.map((header, index) => [header, values[index] || ""]));
  });
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

function splitIds(value) {
  return value
    .split(/[\s,;]+/)
    .map((id) => id.trim())
    .filter(Boolean);
}

function validateCardId(cardId) {
  return /^[A-Za-z0-9_]+$/.test(cardId);
}

async function fileExists(filePath) {
  try {
    await fs.access(filePath);
    return true;
  } catch {
    return false;
  }
}

function shouldRetry(failure) {
  const text = `${failure.stdout_tail || ""}\n${failure.stderr_tail || ""}`;
  return /429|5\d\d|timeout|timed out|fetch failed|network|ECONNRESET|ETIMEDOUT|EAI_AGAIN/i.test(text);
}

function retryDelayMs(attempt) {
  const jitter = Math.round(Math.random() * retryBaseMs * 0.35);
  return retryBaseMs * 2 ** (attempt - 1) + jitter;
}

function countStatuses(items) {
  return items.reduce((counts, item) => {
    counts[item.status] = (counts[item.status] || 0) + 1;
    return counts;
  }, {});
}

function tail(text, maxLength = 1800) {
  return text.length > maxLength ? text.slice(-maxLength) : text;
}

function timestamp() {
  return new Date().toISOString().replace(/[:.]/g, "-");
}

function readableIdentifier(value) {
  return value
    .replace(/^gwent_/, "")
    .split("_")
    .filter(Boolean)
    .map((word) => word[0].toUpperCase() + word.slice(1))
    .join(" ");
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function clampInt(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function envInt(name, fallback) {
  const parsed = Number.parseInt(envValue(name), 10);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function envFlag(name) {
  const value = envValue(name).toLowerCase();
  return value === "1" || value === "true" || value === "yes";
}

function envFlagDefault(name, fallback) {
  const value = envValue(name).toLowerCase();
  if (!value) return fallback;
  return value === "1" || value === "true" || value === "yes";
}

function envValue(name) {
  return (process.env[name] || "").trim();
}
