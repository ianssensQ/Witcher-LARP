import fs from "node:fs";

const DEFAULT_ENV_PATH = "C:\\ianssens\\projects\\AI_OS-1\\.env";

export function loadExternalEnv(envPath = process.env.WITCHER_ASSET_ENV ?? DEFAULT_ENV_PATH) {
  if (!fs.existsSync(envPath)) {
    throw new Error(`Env file not found: ${envPath}`);
  }

  const parsed = {};
  const lines = fs.readFileSync(envPath, "utf8").split(/\r?\n/);

  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;

    const match = trimmed.match(/^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$/);
    if (!match) continue;

    const [, key, rawValue] = match;
    parsed[key] = unquoteEnvValue(rawValue.trim());
  }

  return {
    path: envPath,
    values: parsed,
  };
}

export function requireEnv(env, name) {
  const value = env.values[name];
  if (!value || !value.trim()) {
    throw new Error(`Missing required env variable: ${name}`);
  }
  return value.trim();
}

export function hasEnv(env, name) {
  const value = env.values[name];
  return Boolean(value && value.trim());
}

function unquoteEnvValue(value) {
  if (
    (value.startsWith('"') && value.endsWith('"')) ||
    (value.startsWith("'") && value.endsWith("'"))
  ) {
    return value.slice(1, -1);
  }
  return value;
}
