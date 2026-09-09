import { type ReactNode } from "react";

import { ROLE_LABEL } from "../domain/workflow";
import { type Identity } from "../state/session";
import { type Go, type Route } from "./nav";

export function Shell({
  go,
  center,
  right,
  children,
}: {
  go: Go;
  center?: ReactNode;
  right?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="app">
      <header className="shell-bar">
        <button type="button" className="shell-mark" onClick={() => go({ screen: "schedule" })}>
          EDLO
        </button>
        <div className="shell-center">{center}</div>
        <div className="shell-right">{right}</div>
      </header>
      {children}
    </div>
  );
}

export function Tabs({
  route,
  go,
  episodeTitle,
}: {
  route: Route;
  go: Go;
  episodeTitle?: string;
}) {
  return (
    <nav className="tabs">
      <button
        type="button"
        className={`tab${route.screen === "schedule" ? " tab-on" : ""}`}
        onClick={() => go({ screen: "schedule" })}
      >
        Schedule
      </button>
      {route.screen === "episode" && (
        <button type="button" className="tab tab-on tab-episode" onClick={() => go(route)}>
          {episodeTitle ?? "Episode"}
        </button>
      )}
    </nav>
  );
}

export function Avatar({ initials }: { initials: string }) {
  return (
    <span className="avatar" aria-hidden="true">
      {initials}
    </span>
  );
}

function initialsOf(name: string): string {
  const parts = name.trim().split(/\s+/);
  const letters = parts.length > 1 ? parts[0][0] + parts[parts.length - 1][0] : name.slice(0, 2);
  return letters.toUpperCase();
}

export function Who({ me, onSignOut }: { me: Identity; onSignOut: () => void }) {
  return (
    <span className="who">
      <span className="who-text">
        {me.name}
        <span className="who-role">{ROLE_LABEL[me.role]}</span>
      </span>
      <Avatar initials={initialsOf(me.name)} />
      <button type="button" className="link who-out" onClick={onSignOut}>
        Sign out
      </button>
    </span>
  );
}
