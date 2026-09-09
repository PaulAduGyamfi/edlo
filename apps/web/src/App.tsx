import { useCallback, useEffect, useState } from "react";

import "./styles/ui.css";
import "./styles/app.css";
import { EpisodesProvider } from "./components/EpisodesProvider";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { SessionProvider } from "./components/SessionProvider";
import { ToastProvider } from "./components/ToastProvider";
import { EpisodeScreen } from "./screens/EpisodeScreen";
import { ScheduleScreen } from "./screens/ScheduleScreen";
import { SignInScreen } from "./screens/SignInScreen";
import { type Go, hashFromRoute, type Route, routeFromHash } from "./screens/nav";
import { useSession } from "./state/session";

function useHashRoute(): [Route, Go] {
  const [route, setRoute] = useState<Route>(() => routeFromHash(window.location.hash));
  useEffect(() => {
    const onChange = () => setRoute(routeFromHash(window.location.hash));
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);
  const go = useCallback<Go>((next) => {
    window.location.hash = hashFromRoute(next);
  }, []);
  return [route, go];
}

function Screens() {
  const [route, go] = useHashRoute();
  return route.screen === "episode" ? <EpisodeScreen id={route.id} go={go} /> : <ScheduleScreen go={go} />;
}

function Gate() {
  const { status } = useSession();
  if (status === "checking") {
    return (
      <div className="splash" aria-busy="true">
        <span className="shell-mark">EDLO</span>
        <span className="splash-sub">Checking your session…</span>
      </div>
    );
  }
  if (status === "anonymous") return <SignInScreen />;
  return (
    <EpisodesProvider>
      <Screens />
    </EpisodesProvider>
  );
}

function App() {
  return (
    <ErrorBoundary>
      <ToastProvider>
        <SessionProvider>
          <Gate />
        </SessionProvider>
      </ToastProvider>
    </ErrorBoundary>
  );
}

export default App;
