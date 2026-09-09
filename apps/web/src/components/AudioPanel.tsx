import { useState } from "react";

import { type ApiError, toApiError } from "../api/client";
import { type AudioKind, downloadAudio } from "../api/episodes";
import { type Episode } from "../state/episodes";
import { useToast } from "../state/toast";
import { Banner } from "./Banner";
import { ErrorDetail } from "./ErrorDetail";

const KINDS: { kind: AudioKind; label: string; hint: string }[] = [
  { kind: "rough", label: "Rough mix", hint: "Uploaded when the episode was registered." },
  { kind: "final", label: "Final mix", hint: "What the video editor cuts to." },
];

type Known = "unknown" | "present" | "absent";

type RowState = { known: Known; downloading: boolean; error: ApiError | null };

const initial = (): RowState => ({ known: "unknown", downloading: false, error: null });

/**
 * Download only. The API does not list uploads, so a row only knows what a
 * download in this session found (or did not find).
 */
export function AudioPanel({ episode }: { episode: Episode }) {
  const toast = useToast();
  const [rows, setRows] = useState<Record<AudioKind, RowState>>({ rough: initial(), final: initial() });

  const update = (kind: AudioKind, part: Partial<RowState>) =>
    setRows((r) => ({ ...r, [kind]: { ...r[kind], ...part } }));

  async function download(kind: AudioKind) {
    update(kind, { downloading: true, error: null });
    try {
      const name = await downloadAudio(episode.id, kind);
      update(kind, { known: "present" });
      toast.push({ kind: "info", title: `Downloading ${name}` });
    } catch (e) {
      const err = toApiError(e);
      if (err.status === 404) update(kind, { known: "absent", error: null });
      else update(kind, { error: err });
    } finally {
      update(kind, { downloading: false });
    }
  }

  return (
    <div className="audio">
      {KINDS.map(({ kind, label, hint }) => {
        const row = rows[kind];
        return (
          <div key={kind} className={`audio-row audio-${row.known}`}>
            <span className={`signal signal-${row.known}`} aria-hidden="true">
              <i />
              <i />
              <i />
              <i />
            </span>
            <div className="audio-text">
              <strong>{label}</strong>
              <span className="audio-meta">
                {row.known === "absent" ? "Nothing uploaded yet." : row.known === "present" ? "On the server." : hint}
              </span>
              {row.error && (
                <Banner kind="error">
                  <ErrorDetail
                    error={row.error}
                    lead={row.error.status >= 500 || row.error.status === 0 ? "The server couldn't serve the file." : undefined}
                    onRetry={() => void download(kind)}
                  />
                </Banner>
              )}
            </div>
            <div className="audio-actions">
              <button
                type="button"
                className="btn btn-sm btn-accent"
                disabled={row.downloading || row.known === "absent"}
                onClick={() => void download(kind)}
              >
                {row.downloading ? "Fetching…" : "Download"}
              </button>
            </div>
          </div>
        );
      })}
    </div>
  );
}
