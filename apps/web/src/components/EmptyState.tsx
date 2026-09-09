import "./board-ui.css";

export function EmptyState({ onCreate }: { onCreate: () => void }) {
  return (
    <div className="empty-state">
      <h2>No episodes yet</h2>
      <p>
        Register a recording and it shows up here with a posting date and a
        countdown against it.
      </p>
      <button type="button" className="empty-state-action" onClick={onCreate}>
        Register an episode
      </button>
    </div>
  );
}
