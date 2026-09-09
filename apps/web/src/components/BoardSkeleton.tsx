import "./board-ui.css";

// Placeholder card counts per column — uneven on purpose, so the loading
// state reads as a board rather than a grid of identical grey blocks.
const PLACEHOLDER_COLUMNS = [3, 2, 2, 3, 1, 2];

export function BoardSkeleton() {
  return (
    <div className="board board-skeleton" aria-busy="true" aria-label="Loading episodes">
      <div className="columns">
        {PLACEHOLDER_COLUMNS.map((cards, column) => (
          <section key={column} className="column">
            <div className="skeleton skeleton-heading" />
            {Array.from({ length: cards }, (_, card) => (
              <div key={card} className="skeleton skeleton-card" />
            ))}
          </section>
        ))}
      </div>
    </div>
  );
}
