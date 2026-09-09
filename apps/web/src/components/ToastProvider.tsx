import { type ReactNode, useCallback, useEffect, useMemo, useRef, useState } from "react";

import { type Toast, ToastContext, type ToastInput } from "../state/toast";

const LIFETIME_MS: Record<Toast["kind"], number> = {
  info: 5000,
  success: 5000,
  error: 9000,
};

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const nextId = useRef(1);
  const timers = useRef(new Map<number, number>());

  const dismiss = useCallback((id: number) => {
    const t = timers.current.get(id);
    if (t !== undefined) window.clearTimeout(t);
    timers.current.delete(id);
    setToasts((all) => all.filter((x) => x.id !== id));
  }, []);

  const push = useCallback(
    (input: ToastInput) => {
      const id = nextId.current++;
      setToasts((all) => [...all.slice(-3), { ...input, id }]);
      timers.current.set(
        id,
        window.setTimeout(() => dismiss(id), LIFETIME_MS[input.kind]),
      );
    },
    [dismiss],
  );

  useEffect(() => {
    const pending = timers.current;
    return () => pending.forEach((t) => window.clearTimeout(t));
  }, []);

  const value = useMemo(() => ({ toasts, push, dismiss }), [toasts, push, dismiss]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="toasts" aria-live="polite">
        {toasts.map((t) => (
          <div
            key={t.id}
            className={`toast toast-${t.kind}`}
            role={t.kind === "error" ? "alert" : "status"}
          >
            <span className="toast-dot" aria-hidden="true" />
            <div className="toast-body">
              <strong>{t.title}</strong>
              {t.detail && <span className="toast-detail">{t.detail}</span>}
              {t.traceId && <code className="trace">ref {t.traceId.slice(0, 12)}</code>}
            </div>
            <button
              type="button"
              className="toast-close"
              aria-label="Dismiss"
              onClick={() => dismiss(t.id)}
            >
              ×
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}
