import { lazy, Suspense, useEffect } from "react";

const LordLoginRoute = lazy(() => import("./routes/LordLoginRoute"));
const LordHomeRoute = lazy(() => import("./routes/LordHomeRoute"));
const LordMapRoute = lazy(() => import("./routes/LordMapRoute"));
const LordBattleScreen = lazy(() => import("./LordBattleScreen"));

function App() {
  const path = window.location.pathname;

  if (path === "/lords/login") {
    return (
      <Suspense fallback={<div className="lord-route-loading" aria-label="????????" />}>
        <LordLoginRoute />
      </Suspense>
    );
  }

  if (path === "/lords/battle") {
    return (
      <Suspense fallback={<div className="lord-route-loading" aria-label="????????" />}>
        <LordBattleScreen />
      </Suspense>
    );
  }

  if (path === "/lords/map") {
    return (
      <Suspense fallback={<div className="lord-route-loading" aria-label="????????" />}>
        <LordMapRoute />
      </Suspense>
    );
  }

  if (path === "/lords/home") {
    return (
      <Suspense fallback={<div className="lord-route-loading" aria-label="????????" />}>
        <LordHomeRoute />
      </Suspense>
    );
  }

  if (path === "/lords" || path === "/lords/castle" || path === "/lords/dashboard") {
    return <RedirectTo path="/lords/home" />;
  }

  return <RedirectTo path="/lords/login" />;
}

function RedirectTo({ path }: { path: string }) {
  useEffect(() => {
    window.location.replace(path);
  }, [path]);

  return null;
}

export default App;
