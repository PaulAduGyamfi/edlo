import { createContext, useContext } from "react";

import { toApiError } from "../api/client";

export type ToastKind = "info" | "success" | "error";

export type Toast = {
  id: number;
  kind: ToastKind;
  title: string;
  detail?: string;
  traceId?: string | null;
};

export type ToastInput = Omit<Toast, "id">;

export type ToastApi = {
  toasts: Toast[];
  push: (t: ToastInput) => void;
  dismiss: (id: number) => void;
};

export const ToastContext = createContext<ToastApi | null>(null);

export function useToast(): ToastApi {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used inside ToastProvider");
  return ctx;
}

/** One-liner for catch blocks: `toast.push(errorToast(e, "Couldn't move the episode"))`. */
export function errorToast(e: unknown, title: string): ToastInput {
  const err = toApiError(e);
  return { kind: "error", title, detail: err.detail, traceId: err.traceId };
}
