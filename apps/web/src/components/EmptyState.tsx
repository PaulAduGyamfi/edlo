import "./board-ui.css";

export function EmptyState({ onCreate }: { onCreate: (() => void) | null }) {
  return (
    <div className="empty-state">
      <h2>No episodes yet</h2>
      <p>
        Register a recording and it shows up here with a posting date and a
        countdown against it.
      </p>
      {onCreate ? (
        <button type="button" className="empty-state-action" onClick={onCreate}>
          Register an episode
        </button>
      ) : (
        <p className="empty-state-note">Only the audio editor or owner can register one.</p>
      )}
    </div>
  );
}
