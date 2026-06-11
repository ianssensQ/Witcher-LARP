export type LordRuntimeSession = {
  lordId: string;
  roleToken: string;
  domainId?: string;
};

export type LordRuntimeQueryOptions = {
  lordId?: string;
};

export const lordRuntimeApiStorageKey = "witcher_larp_api_base_url";
export const lordRuntimeStateCachePrefix = "witcher_larp_lord_state_cache_v1";
export const lordRuntimeProductionPort = "8002";
export const lordRuntimeRequestTimeoutMs = 6_000;

const lordRuntimeLordIdStorageKey = "witcher_larp_lord_id";
const lordRuntimeRoleTokenStorageKey = "witcher_larp_role_token";
const lordRuntimeDomainIdStorageKey = "witcher_larp_domain_id";
const lordRuntimeSensitiveQueryKeys = ["token", "role_token", "roleToken"];

export const normalizeLordRuntimeApiBaseUrl = (value: string | null | undefined) =>
  (value || "").trim().replace(/\/$/, "");

export const isLordRuntimeProductionOrigin = () =>
  window.location.protocol.startsWith("http") && window.location.port === lordRuntimeProductionPort;

export const getLordRuntimeApiBaseUrl = (routeParams: URLSearchParams) => {
  if (isLordRuntimeProductionOrigin()) {
    localStorage.removeItem(lordRuntimeApiStorageKey);
    return "";
  }

  const queryApiBaseUrl = normalizeLordRuntimeApiBaseUrl(routeParams.get("api"));
  if (queryApiBaseUrl) {
    localStorage.setItem(lordRuntimeApiStorageKey, queryApiBaseUrl);
    return queryApiBaseUrl;
  }

  return normalizeLordRuntimeApiBaseUrl(
    localStorage.getItem(lordRuntimeApiStorageKey) || import.meta.env.VITE_API_BASE_URL
  );
};

export const withLordRuntimeQuery = (
  path: string,
  apiBaseUrl: string,
  options: LordRuntimeQueryOptions = {}
) => {
  const normalizedApiBaseUrl = isLordRuntimeProductionOrigin() ? "" : normalizeLordRuntimeApiBaseUrl(apiBaseUrl);
  const url = new URL(path, window.location.origin);
  if (normalizedApiBaseUrl) {
    url.searchParams.set("api", normalizedApiBaseUrl);
  }
  if (options.lordId) {
    url.searchParams.set("lord", options.lordId);
  }
  lordRuntimeSensitiveQueryKeys.forEach((key) => url.searchParams.delete(key));
  return `${url.pathname}${url.search}${url.hash}`;
};

const getRouteLordId = (routeParams: URLSearchParams) =>
  routeParams.get("lord_id") || routeParams.get("lordId") || routeParams.get("lord") || "";

export const readLordRuntimeSession = (routeParams: URLSearchParams = new URLSearchParams(window.location.search)) => {
  const storedLordId = localStorage.getItem(lordRuntimeLordIdStorageKey)?.trim() || "";
  const routeLordId = getRouteLordId(routeParams).trim();
  const roleToken = localStorage.getItem(lordRuntimeRoleTokenStorageKey)?.trim() || "";
  const lordId = storedLordId || routeLordId;

  if (!lordId || !roleToken) {
    return null;
  }

  if (storedLordId && routeLordId && storedLordId !== routeLordId) {
    return null;
  }

  const session: LordRuntimeSession = { lordId, roleToken };
  const domainId = localStorage.getItem(lordRuntimeDomainIdStorageKey)?.trim();
  if (domainId) {
    session.domainId = domainId;
  }
  return session;
};

export const persistLordRuntimeSession = (session: LordRuntimeSession) => {
  localStorage.setItem(lordRuntimeRoleTokenStorageKey, session.roleToken);
  localStorage.setItem(lordRuntimeLordIdStorageKey, session.lordId);
  if (session.domainId) {
    localStorage.setItem(lordRuntimeDomainIdStorageKey, session.domainId);
  }
};

export const clearLordRuntimeSession = (options: { clearApiBaseUrl?: boolean } = {}) => {
  localStorage.removeItem(lordRuntimeRoleTokenStorageKey);
  localStorage.removeItem(lordRuntimeLordIdStorageKey);
  localStorage.removeItem(lordRuntimeDomainIdStorageKey);
  if (options.clearApiBaseUrl) {
    localStorage.removeItem(lordRuntimeApiStorageKey);
  }

  for (let index = localStorage.length - 1; index >= 0; index -= 1) {
    const key = localStorage.key(index);
    if (key?.startsWith(lordRuntimeStateCachePrefix)) {
      localStorage.removeItem(key);
    }
  }
};

export const stripLordRuntimeSensitiveQueryParams = () => {
  const url = new URL(window.location.href);
  let changed = false;

  lordRuntimeSensitiveQueryKeys.forEach((key) => {
    if (url.searchParams.has(key)) {
      url.searchParams.delete(key);
      changed = true;
    }
  });

  if (isLordRuntimeProductionOrigin() && url.searchParams.has("api")) {
    url.searchParams.delete("api");
    changed = true;
  }

  if (changed) {
    window.history.replaceState(window.history.state, "", `${url.pathname}${url.search}${url.hash}`);
  }
};

export const getLordRuntimeCurrentPathWithoutSensitiveParams = () => {
  const url = new URL(window.location.href);
  lordRuntimeSensitiveQueryKeys.forEach((key) => url.searchParams.delete(key));
  if (isLordRuntimeProductionOrigin()) {
    url.searchParams.delete("api");
  }
  return `${url.pathname}${url.search}${url.hash}`;
};

export const getLordRuntimeLoginPath = (apiBaseUrl: string, nextPath?: string) => {
  const url = new URL(withLordRuntimeQuery("/lords/login", apiBaseUrl), window.location.origin);
  if (nextPath?.startsWith("/lords/") && !nextPath.startsWith("/lords/login")) {
    url.searchParams.set("next", nextPath);
  }
  return `${url.pathname}${url.search}${url.hash}`;
};

export const isLordRuntimeAuthResponse = (response: Response) =>
  response.status === 401 || response.status === 403;
