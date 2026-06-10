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
  currentMp: number;
  mpCap: number;
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

const lordMpDefaultLordId = "p_lord_1";
const lordMpDefaultRoleToken = "LORD-NORTH-R8K4";
const lordMpStatePollMs = 15_000;
const lordMpFallbackState: LordMpRuntimeState = {
  currentMp: 6,
  mpCap: 6
};

const clampLordMpMetric = (value: unknown, fallback: number) => {
  const numericValue = Number(value);
  return Number.isFinite(numericValue) ? Math.max(0, Math.floor(numericValue)) : fallback;
};

const normalizeLordMpState = (state: LordMpRuntimeState) => {
  const mpCap = Math.max(1, clampLordMpMetric(state.mpCap, lordMpFallbackState.mpCap));
  const currentMp = Math.min(mpCap, clampLordMpMetric(state.currentMp, lordMpFallbackState.currentMp));
  return { currentMp, mpCap };
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
  const apiBaseUrl = (routeParams.get("api") || import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");
  const lordId =
    routeParams.get("lord_id") ||
    routeParams.get("lordId") ||
    routeParams.get("lord") ||
    localStorage.getItem("witcher_larp_lord_id") ||
    lordMpDefaultLordId;
  const roleToken =
    routeParams.get("token") ||
    localStorage.getItem("witcher_larp_role_token") ||
    lordMpDefaultRoleToken;

  return { apiBaseUrl, lordId, roleToken };
};

export function useLordMpRuntimeState(initialState: LordMpRuntimeState = lordMpFallbackState) {
  const [mpState, setMpState] = useState(() => normalizeLordMpState(initialState));

  const fetchLordMpState = useCallback(async () => {
    const { apiBaseUrl, lordId, roleToken } = getLordMpRuntimeConnection();
    if (!lordId) {
      return;
    }

    try {
      const headers: Record<string, string> = { Accept: "application/json" };
      if (roleToken) {
        headers["X-Role-Token"] = roleToken;
      }

      const response = await fetch(`${apiBaseUrl}/api/lords/${lordId}/state`, { headers });
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
  const visibleFields = Math.min(
    lordMpFillFields.length,
    normalizedState.currentMp
  );

  return (
    <section
      className={`lord-mp-hud${className ? ` ${className}` : ""}`}
      aria-label={`MP ${normalizedState.currentMp}/${normalizedState.mpCap}`}
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
        <span>{normalizedState.currentMp}/{normalizedState.mpCap}</span>
      </div>
    </section>
  );
}
