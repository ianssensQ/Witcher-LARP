export type LordUiMode = "production" | "demo" | "tutorial";

export type LordUiConnectionState = "loading" | "ready" | "stale" | "offline" | "readonly" | "demo";

export type LordMpUiState = {
  currentMp: number | null;
  mpCap: number | null;
  isKnown: boolean;
};

export type LordBackendBattleSummary = Record<string, unknown> & {
  battle_id?: string;
  status?: string;
  queue_state?: string;
};

export type LordBackendStatePayload = Record<string, unknown> & {
  domain?: Record<string, unknown> & {
    current_mp?: unknown;
    mp_cap?: unknown;
  };
  movement?: Record<string, unknown> & {
    current_mp?: unknown;
    mp_cap?: unknown;
  };
  summary?: Record<string, unknown> & {
    active_battles?: unknown;
  };
  battles?: LordBackendBattleSummary[];
};

export type LordActiveBattleUiState = {
  active: boolean;
  battleId: string | null;
  battle: LordBackendBattleSummary | null;
};

export type LordUiState = {
  mode: LordUiMode;
  connection: LordUiConnectionState;
  hasAuthoritativeState: boolean;
  isDemo: boolean;
  isReadOnly: boolean;
  readonlyReason: string;
  mp: LordMpUiState;
  activeBattle: LordActiveBattleUiState;
};

export type LordStateAdapterOptions = {
  mode?: LordUiMode;
};
