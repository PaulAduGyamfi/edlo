import { type ReactNode } from "react";

import { type Go, type Screen } from "./nav";

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
        <button type="button" className="shell-mark" onClick={() => go("session")}>
          EDLO
        </button>
        <div className="shell-center">{center}</div>
        <div className="shell-right">{right}</div>
      </header>
      {children}
    </div>
  );
}

const TABS: [Screen, string][] = [
  ["session", "This episode"],
  ["archive", "Archive"],
  ["schedule", "Schedule"],
];

export function Tabs({ active, go }: { active: Screen; go: Go }) {
  return (
    <nav className="tabs">
      {TABS.map(([screen, label]) => (
        <button
          type="button"
          key={screen}
          className={`tab${active === screen ? " tab-on" : ""}`}
          onClick={() => go(screen)}
        >
          {label}
        </button>
      ))}
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
