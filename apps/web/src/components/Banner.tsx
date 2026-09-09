import { type ReactNode } from "react";

import "./board-ui.css";

type BannerKind = "info" | "warn" | "error";

export function Banner({
  kind = "info",
  children,
}: {
  kind?: BannerKind;
  children: ReactNode;
}) {
  return (
    <div
      className={`banner banner-${kind}`}
      role={kind === "error" ? "alert" : "status"}
    >
      <span className="banner-dot" aria-hidden="true" />
      <div className="banner-body">{children}</div>
    </div>
  );
}
