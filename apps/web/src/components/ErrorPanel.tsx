import { type ApiError } from "../api/client";

export function ErrorPanel({
  error,
  onRetry,
}: {
  error: ApiError;
  onRetry: () => void;
}) {
  return (
    <div className="error-panel">
      <h2>{error.retryable ? "Something went wrong" : "That didn't work"}</h2>
      <p>{error.detail}</p>
      {error.retryable && <button onClick={onRetry}>Try again</button>}
      {/* Small, grey, always present. Turns "it broke" into a 30-second fix. */}
      {error.traceId && (
        <code className="trace">ref {error.traceId.slice(0, 12)}</code>
      )}
    </div>
  );
}