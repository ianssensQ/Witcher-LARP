import { useCallback, useEffect, useState } from "react";

import lordHomeMpFillField1 from "./assets/generated/lords-home/ui/mp-widget-fill-field-1-v5.png";
import lordHomeMpFillField2 from "./assets/generated/lords-home/ui/mp-widget-fill-field-2-v5.png";
import lordHomeMpFillField3 from "./assets/generated/lords-home/ui/mp-widget-fill-field-3-v5.png";
import lordHomeMpFillField4 from "./assets/generated/lords-home/ui/mp-widget-fill-field-4-v5.png";
import lordHomeMpFillField5 from "./assets/generated/lords-home/ui/mp-widget-fill-field-5-v5.png";
import lordHomeMpFillField6 from "./assets/generated/lords-home/ui/mp-widget-fill-field-6-v5.png";
import lordHomeMpFillField7 from "./assets/generated/lords-home/ui/mp-widget-fill-field-7-v5.png";
import lordHomeMpFillField8 from "./assets/generated/lords-home/ui/mp-widget-fill-field-8-v5.png";
import lordHomeMpWidgetFrame from "./assets/generated/lords-home/ui/mp-widget-frame-transparent-v5.png";
import { getLordRuntimeApiBaseUrl, readLordRuntimeSession } from "./lordRuntime";

type LordMpRuntimePayload = {
  domain?: {
    current_mp?: number;
    mp_cap?: number;
  };
  movement?: {
    current_mp?: number;
    mp_cap?: number;
  };
};

export type LordMpRuntimeState = {
  currentMp: number | null;
  mpCap: number | null;
  isKnown?: boolean;
};

type LordMpHudProps = LordMpRuntimeState & {
  className?: string;
};

const lordMpFillFields = [
  lordHomeMpFillField1,
  lordHomeMpFillField2,
  lordHomeMpFillField3,
  lordHomeMpFillField4,
  lordHomeMpFillField5,
  lordHomeMpFillField6,
  lordHomeMpFillField7,
  lordHomeMpFillField8
];

const lordMpStatePollMs = 3_000;
const lordMpFallbackState: LordMpRuntimeState = {
  currentMp: null,
  mpCap: null,
  isKnown: false
};

const clampLordMpMetric = (value: unknown, fallback: number | null) => {
  const numericValue = Number(value);
  return Number.isFinite(numericValue) ? Math.max(0, Math.floor(numericValue)) : fallback;
};

const normalizeLordMpState = (state: LordMpRuntimeState) => {
  const rawMpCap = clampLordMpMetric(state.mpCap, null);
  const rawCurrentMp = clampLordMpMetric(state.currentMp, null);
  if (rawMpCap === null || rawCurrentMp === null) {
    return { currentMp: null, mpCap: null, isKnown: false };
  }
  const mpCap = Math.max(1, rawMpCap);
  const currentMp = Math.min(mpCap, rawCurrentMp);
  return { currentMp, mpCap, isKnown: true };
};

export const extractLordMpRuntimeState = (
  payload: LordMpRuntimePayload | null | undefined,
  fallback: LordMpRuntimeState = lordMpFallbackState
) => normalizeLordMpState({
  currentMp: payload?.movement?.current_mp ?? payload?.domain?.current_mp ?? fallback.currentMp,
  mpCap: payload?.movement?.mp_cap ?? payload?.domain?.mp_cap ?? fallback.mpCap
});

const getLordMpRuntimeConnection = () => {
  const routeParams = new URLSearchParams(window.location.search);
  const session = readLordRuntimeSession(routeParams);

  return {
    apiBaseUrl: getLordRuntimeApiBaseUrl(routeParams),
    lordId: session?.lordId ?? "",
    roleToken: session?.roleToken ?? ""
  };
};

export function useLordMpRuntimeState(initialState: LordMpRuntimeState = lordMpFallbackState) {
  const [mpState, setMpState] = useState(() => normalizeLordMpState(initialState));

  const fetchLordMpState = useCallback(async () => {
    const { apiBaseUrl, lordId, roleToken } = getLordMpRuntimeConnection();
    if (!lordId || !roleToken) {
      return;
    }

    try {
      const headers: Record<string, string> = { Accept: "application/json" };
      if (roleToken) {
        headers["X-Role-Token"] = roleToken;
      }

      const response = await fetch(`${apiBaseUrl}/api/lords/${lordId}/summary`, { headers });
      const payload: unknown = await response.json().catch(() => null);
      if (!response.ok) {
        return;
      }

      setMpState((current) => extractLordMpRuntimeState(payload as LordMpRuntimePayload | null, current));
    } catch {
      // Keep the last known MP value on static screens if the local runtime is offline.
    }
  }, []);

  useEffect(() => {
    void fetchLordMpState();
    const intervalId = window.setInterval(fetchLordMpState, lordMpStatePollMs);
    return () => window.clearInterval(intervalId);
  }, [fetchLordMpState]);

  return mpState;
}

export function LordMpHud({ currentMp, mpCap, className = "" }: LordMpHudProps) {
  const normalizedState = normalizeLordMpState({ currentMp, mpCap });
  const visibleCurrentMp = normalizedState.currentMp ?? 0;
  const visibleFields = Math.min(
    lordMpFillFields.length,
    visibleCurrentMp
  );
  const caption = normalizedState.isKnown ? `${normalizedState.currentMp}/${normalizedState.mpCap}` : "--/--";

  return (
    <section
      className={`lord-mp-hud${className ? ` ${className}` : ""}`}
      aria-label={`MP ${caption}`}
    >
      <div className="lord-mp-hud-backdrop" aria-hidden="true" />
      <div className="lord-mp-hud-rect-layer" aria-hidden="true">
        {lordMpFillFields.map((src, index) =>
          index < visibleFields ? (
            <img key={src} className="lord-mp-hud-fill-field" src={src} alt="" draggable={false} />
          ) : null
        )}
      </div>
      <img className="lord-mp-hud-frame" src={lordHomeMpWidgetFrame} alt="" draggable={false} />
      <div className="lord-mp-hud-caption">
        <b>MP</b>
        <span>{caption}</span>
      </div>
    </section>
  );
}
