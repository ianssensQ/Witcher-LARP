import { useEffect, useRef, useState } from "react";
import type { FormEvent, MouseEvent } from "react";
import { AnimatePresence, motion, useAnimationControls, useReducedMotion } from "motion/react";
import lordLoginBackground from "../assets/generated/lords-login/login-background-warcraft.png";
import lordLoginLogo from "../assets/generated/lords-login/witcher-larp-logo.png";
import lordLoginMenuFrameLong from "../assets/generated/lords-login/menu-frame-warcraft-login.png";
import lordLoginMenuFrame from "../assets/generated/lords-login/menu-frame-warcraft.png";
import { getLordRuntimeApiBaseUrl, getLordRuntimeCurrentPathWithoutSensitiveParams, isLordRuntimeAuthResponse, persistLordRuntimeSession, stripLordRuntimeSensitiveQueryParams, withLordRuntimeQuery } from "../lordRuntime";

type AnimatedLordLoginMode = "menu" | "login" | "onboarding";
type AnimatedLordMenuTarget = "enter" | "training";

type LordRoleTokenAuth = {
  role_type?: string;
  owner_id?: string;
  lord_id?: string | null;
  domain_id?: string | null;
  display_name?: string;
};

const lordLoginCopy = {
  enter: "\u0412\u0445\u043e\u0434",
  training: "\u041e\u0431\u0443\u0447\u0435\u043d\u0438\u0435",
  lordCode: "\u041a\u043e\u0434 \u043b\u043e\u0440\u0434\u0430",
  codePlaceholder: "\u0412\u0432\u0435\u0434\u0438\u0442\u0435 \u043a\u043e\u0434",
  submit: "\u0412\u043e\u0439\u0442\u0438",
  back: "\u041d\u0430\u0437\u0430\u0434",
  emptyCode: "\u0412\u0432\u0435\u0434\u0438\u0442\u0435 \u043a\u043e\u0434 \u043b\u043e\u0440\u0434\u0430",
  invalidCode: "\u041d\u0435\u0432\u0435\u0440\u043d\u044b\u0439 \u043a\u043e\u0434 \u043b\u043e\u0440\u0434\u0430",
  beforeGame: "\u041f\u0435\u0440\u0435\u0434 \u0438\u0433\u0440\u043e\u0439",
  onboarding:
    "\u0412\u043e\u0439\u0434\u0438\u0442\u0435 \u043f\u043e \u043a\u043e\u0434\u0443 \u043b\u043e\u0440\u0434\u0430 \u043d\u0430 \u0441\u0432\u043e\u0435\u043c \u043a\u043e\u043c\u043f\u044c\u044e\u0442\u0435\u0440\u0435. \u041f\u043e\u0441\u043b\u0435 \u0432\u0445\u043e\u0434\u0430 \u043e\u0442\u043a\u0440\u043e\u0435\u0442\u0441\u044f \u0432\u043b\u0430\u0434\u0435\u043d\u0438\u0435, \u043a\u0430\u0440\u0442\u0430 \u0438 \u0430\u0440\u043c\u0438\u044f."
} as const;

const normalizeLordAccessCode = (value: string) => value.trim().replace(/\s+/g, "").toLocaleUpperCase("ru-RU");

const preventLordLoginContextMenu = (event: MouseEvent<HTMLElement>) => {
  const target = event.target;

  if (target instanceof HTMLElement && target.closest("input, textarea")) {
    return;
  }

  event.preventDefault();
};

function AnimatedLordLoginScreen() {
  const queryParams = new URLSearchParams(window.location.search);
  stripLordRuntimeSensitiveQueryParams();
  const requestedView = queryParams.get("view");
  const apiBaseUrl = getLordRuntimeApiBaseUrl(queryParams);
  const requestedNext = queryParams.get("next");
  const nextPath = requestedNext?.startsWith("/lords/") ? requestedNext : "/lords/home";
  const initialMode: AnimatedLordLoginMode =
    requestedView === "login" || requestedView === "onboarding" ? requestedView : "menu";
  const [mode, setMode] = useState<AnimatedLordLoginMode>(initialMode);
  const [code, setCode] = useState("");
  const [loginError, setLoginError] = useState(queryParams.get("error") === "login" ? lordLoginCopy.invalidCode : "");
  const [isSubmittingLogin, setIsSubmittingLogin] = useState(false);
  const [isTransitioning, setIsTransitioning] = useState(false);
  const [pressedTarget, setPressedTarget] = useState<AnimatedLordMenuTarget | null>(null);
  const codeInputRef = useRef<HTMLInputElement>(null);
  const panelControls = useAnimationControls();
  const prefersReducedMotion = useReducedMotion();
  const previewHover = queryParams.get("hover");
  const motionScale = queryParams.get("motion") === "slow" ? 1.75 : 1;

  const movePanelTo = async (nextMode: AnimatedLordLoginMode, target: AnimatedLordMenuTarget | null = null) => {
    if (isTransitioning || nextMode === mode) {
      return;
    }

    setIsTransitioning(true);
    setPressedTarget(target);

    if (!prefersReducedMotion) {
      await panelControls.start({
        y: 12,
        rotate: -0.45,
        transition: { duration: 0.12 * motionScale, ease: "easeOut" }
      });
      await panelControls.start({
        y: "-118vh",
        rotate: 2.2,
        transition: { duration: 0.54 * motionScale, ease: [0.74, 0, 0.28, 1] }
      });
    }

    setMode(nextMode);
    setPressedTarget(null);

    if (!prefersReducedMotion) {
      panelControls.set({ y: "-118vh", rotate: -1.6 });
      await panelControls.start({
        y: 20,
        rotate: 0.7,
        transition: { duration: 0.62 * motionScale, ease: [0.12, 0.82, 0.22, 1] }
      });
      await panelControls.start({
        y: 0,
        rotate: 0,
        transition: { type: "spring", stiffness: 160 / motionScale, damping: 10, mass: 1.1 }
      });
    }

    setIsTransitioning(false);
  };

  const focusCodeInput = () => {
    codeInputRef.current?.focus({ preventScroll: true });
  };

  const handleCodeChange = (value: string) => {
    setCode(value);

    if (loginError) {
      setLoginError("");
    }
  };

  const handleLoginSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();

    const normalizedCode = normalizeLordAccessCode(code);

    if (!normalizedCode) {
      setLoginError(lordLoginCopy.emptyCode);
      window.setTimeout(focusCodeInput, 0);
      return;
    }

    setIsSubmittingLogin(true);

    try {
      const response = await fetch(`${apiBaseUrl}/api/auth/role-token`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({ token: normalizedCode })
      });
      const payload: unknown = await response.json().catch(() => null);
      if (!response.ok) {
        throw new Error(lordLoginCopy.invalidCode);
      }

      const auth = payload as LordRoleTokenAuth;
      const lordId = auth.lord_id || auth.owner_id;
      if (auth.role_type !== "lord" || !lordId) {
        throw new Error(lordLoginCopy.invalidCode);
      }

      persistLordRuntimeSession({
        lordId,
        roleToken: normalizedCode,
        domainId: auth.domain_id || undefined
      });
      setLoginError("");
      window.location.assign(withLordRuntimeQuery(nextPath, apiBaseUrl));
    } catch (error) {
      setLoginError(error instanceof Error ? error.message : lordLoginCopy.invalidCode);
      window.setTimeout(focusCodeInput, 0);
    } finally {
      setIsSubmittingLogin(false);
    }
  };

  const openTrainingBuild = () => {
    window.location.assign(withLordRuntimeQuery("/lords/home?training=1", apiBaseUrl));
  };

  useEffect(() => {
    if (queryParams.get("auto") !== "login" || mode !== "menu") {
      return;
    }

    const timer = window.setTimeout(() => {
      void movePanelTo("login", "enter");
    }, 240);

    return () => window.clearTimeout(timer);
  }, []);

  return (
    <main className="lord-login-screen" onContextMenu={preventLordLoginContextMenu}>
      <motion.div
        className="lord-login-bg"
        aria-hidden="true"
        style={{ backgroundImage: `url(${lordLoginBackground})` }}
        animate={prefersReducedMotion ? undefined : { scale: [1.02, 1.045, 1.02] }}
        transition={{ duration: 28, repeat: Infinity, ease: "easeInOut" }}
      />
      <motion.div
        className="lord-login-mist"
        animate={prefersReducedMotion ? undefined : { opacity: [0.82, 1, 0.86] }}
        transition={{ duration: 12, repeat: Infinity, ease: "easeInOut" }}
      />
      <motion.img
        className="lord-login-logo-image"
        src={lordLoginLogo}
        alt="Witcher LARP I"
        draggable={false}
        animate={
          prefersReducedMotion
            ? undefined
            : {
                filter: [
                  "drop-shadow(0 12px 0 rgba(0, 0, 0, .34)) drop-shadow(0 24px 38px rgba(0, 0, 0, .82)) drop-shadow(0 0 16px rgba(128, 202, 255, .16))",
                  "drop-shadow(0 12px 0 rgba(0, 0, 0, .34)) drop-shadow(0 24px 38px rgba(0, 0, 0, .82)) drop-shadow(0 0 30px rgba(128, 202, 255, .34))",
                  "drop-shadow(0 12px 0 rgba(0, 0, 0, .34)) drop-shadow(0 24px 38px rgba(0, 0, 0, .82)) drop-shadow(0 0 16px rgba(128, 202, 255, .16))"
                ]
              }
        }
        transition={{ duration: 5.8, repeat: Infinity, ease: "easeInOut" }}
      />

      <motion.aside
        className={`lord-menu-sign${mode === "login" ? " is-login-panel" : ""}`}
        animate={panelControls}
        initial={{ y: 0, rotate: 0 }}
        style={{ transformOrigin: "50% 5%" }}
        aria-busy={isTransitioning}
      >
        <span className="lord-rise-chain lord-rise-chain-left" aria-hidden="true" />
        <span className="lord-rise-chain lord-rise-chain-right" aria-hidden="true" />
        <img className="lord-menu-art" src={mode === "login" ? lordLoginMenuFrameLong : lordLoginMenuFrame} alt="" draggable={false} />
        <div className="lord-menu-frame">
          <AnimatePresence mode="wait">
            {mode === "menu" ? (
              <motion.div
                key="menu"
                className="lord-menu-buttons lord-panel-content"
                initial={{ opacity: 0, y: 14 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -16 }}
                transition={{ duration: 0.24 * motionScale }}
              >
                <button
                  className={`lord-slot-button${previewHover === "enter" ? " is-hover" : ""}${pressedTarget === "enter" ? " is-pressed" : ""}`}
                  onClick={() => void movePanelTo("login", "enter")}
                  disabled={isTransitioning}
                  aria-label={lordLoginCopy.enter}
                >
                  <span data-label={lordLoginCopy.enter}>{lordLoginCopy.enter}</span>
                </button>
                <button
                  className={`lord-slot-button${previewHover === "training" ? " is-hover" : ""}${pressedTarget === "training" ? " is-pressed" : ""}`}
                  onClick={openTrainingBuild}
                  disabled={isTransitioning}
                  aria-label={lordLoginCopy.training}
                >
                  <span data-label={lordLoginCopy.training}>{lordLoginCopy.training}</span>
                </button>
              </motion.div>
            ) : null}

            {mode === "login" ? (
              <motion.form
                key="login"
                className="lord-login-form lord-panel-content"
                initial={{ opacity: 0, y: 18 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -14 }}
                transition={{ duration: 0.26 * motionScale }}
                onSubmit={handleLoginSubmit}
              >
                <label
                  className="lord-code-slot"
                  onClick={focusCodeInput}
                  onPointerDown={(event) => {
                    if (event.target !== codeInputRef.current) {
                      event.preventDefault();
                    }
                    focusCodeInput();
                  }}
                >
                  <input
                    autoFocus
                    ref={codeInputRef}
                    aria-label={lordLoginCopy.lordCode}
                    aria-invalid={Boolean(loginError)}
                    aria-describedby={loginError ? "lord-login-error" : undefined}
                    value={code}
                    onChange={(event) => handleCodeChange(event.target.value)}
                    placeholder={lordLoginCopy.codePlaceholder}
                  />
                </label>
                <div className="lord-form-actions">
                  <button className="lord-panel-action-button lord-submit-button" type="submit" disabled={isTransitioning || isSubmittingLogin}>
                    {lordLoginCopy.submit}
                  </button>
                  <button className="lord-panel-action-button lord-back-button" type="button" onClick={() => void movePanelTo("menu")} disabled={isTransitioning || isSubmittingLogin}>
                    {lordLoginCopy.back}
                  </button>
                </div>
                <AnimatePresence>
                  {loginError ? (
                    <motion.p
                      key="lord-login-error"
                      id="lord-login-error"
                      className="lord-login-error"
                      role="alert"
                      initial={{ opacity: 0, y: -6, scale: 0.96 }}
                      animate={{ opacity: 1, y: 0, scale: 1 }}
                      exit={{ opacity: 0, y: 4, scale: 0.97 }}
                      transition={{ duration: 0.18 * motionScale }}
                    >
                      {loginError}
                    </motion.p>
                  ) : null}
                </AnimatePresence>
              </motion.form>
            ) : null}

            {mode === "onboarding" ? (
              <motion.div
                key="onboarding"
                className="lord-onboarding-panel lord-panel-content"
                initial={{ opacity: 0, y: 18 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -14 }}
                transition={{ duration: 0.26 * motionScale }}
              >
                <h1>{lordLoginCopy.beforeGame}</h1>
                <p>{lordLoginCopy.onboarding}</p>
                <button className="lord-panel-action-button" type="button" onClick={() => void movePanelTo("menu")} disabled={isTransitioning}>
                  {lordLoginCopy.back}
                </button>
              </motion.div>
            ) : null}
          </AnimatePresence>
        </div>
      </motion.aside>
    </main>
  );
}

export default AnimatedLordLoginScreen;
