import { type ApiError } from "../api/client";

/** Inline error text: what failed, what the server said, and the ref to quote. */
export function ErrorDetail({
  error,
  lead,
  onRetry,
}: {
  error: ApiError;
  lead?: string;
  onRetry?: () => void;
}) {
  return (
    <span className="error-detail">
      {lead && <strong>{lead} </strong>}
      {error.detail}
      {onRetry && error.retryable && (
        <>
          {" "}
          <button type="button" className="link" onClick={onRetry}>
            Try again
          </button>
        </>
      )}
      {error.traceId && <code className="trace">ref {error.traceId.slice(0, 12)}</code>}
    </span>
  );
}
