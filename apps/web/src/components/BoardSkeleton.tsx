import "./board-ui.css";

// A few rows of uneven width so the loading state reads as a run sheet.
const ROWS = [72, 58, 66, 50, 62];

export function BoardSkeleton() {
  return (
    <div className="run-skeleton" aria-busy="true" aria-label="Loading episodes">
      {ROWS.map((w, i) => (
        <div key={i} className="skeleton skeleton-row" style={{ width: `${w}%` }} />
      ))}
    </div>
  );
}
