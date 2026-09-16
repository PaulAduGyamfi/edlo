import { type ChangeEvent, useEffect, useRef, useState } from "react";

import { type ApiError, toApiError } from "../api/client";
import { type AudioKind, type AudioRow, downloadAudio, listAudio, type Upload, uploadAudio } from "../api/episodes";
import { AUDIO_ACCEPT, fmtBytes, validateAudioFile } from "../lib/audio";
import { fmtStamp } from "../lib/dates";
import { type Episode } from "../state/episodes";
import { useMe } from "../state/session";
import { errorToast, useToast } from "../state/toast";
import { Banner } from "./Banner";
import { ErrorDetail } from "./ErrorDetail";

const KINDS: { kind: AudioKind; label: string; hint: string }[] = [
  { kind: "rough", label: "Rough mix", hint: "Transcribed; the plan is built from it." },
  { kind: "final", label: "Final mix", hint: "What the video editor cuts to. The handoff." },
];

type UploadState = { kind: AudioKind; name: string; fraction: number };

const who = (id: string) => {
  const bare = id.replace(/^u_/, "");
  return bare ? bare[0].toUpperCase() + bare.slice(1) : id;
};

/** What is on the server for each kind, who put it there, whether it was picked up; upload and download. */
export function AudioPanel({ episode }: { episode: Episode }) {
  const me = useMe();
  const toast = useToast();
  const canUpload = me.role !== "video_editor";
  const [rows, setRows] = useState<AudioRow[] | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [downloading, setDownloading] = useState<AudioKind | null>(null);
  const [uploading, setUploading] = useState<UploadState | null>(null);
  const [uploadError, setUploadError] = useState<ApiError | null>(null);
  const upload = useRef<Upload | null>(null);
  const inputs = useRef<Record<AudioKind, HTMLInputElement | null>>({ rough: null, final: null });

  useEffect(() => {
    let cancelled = false;
    listAudio(episode.id).then(
      (data) => {
        if (!cancelled) {
          setRows(data);
          setError(null);
        }
      },
      (e: unknown) => {
        if (!cancelled) setError(toApiError(e));
      },
    );
    return () => {
      cancelled = true;
    };
  }, [episode.id, attempt]);

  useEffect(() => () => upload.current?.abort(), []);

  const refresh = () => setAttempt((n) => n + 1);

  async function download(kind: AudioKind) {
    setDownloading(kind);
    try {
      const name = await downloadAudio(episode.id, kind);
      toast.push({ kind: "info", title: `Downloading ${name}` });
      refresh(); // the first download stamps the handoff
    } catch (e) {
      toast.push(errorToast(e, "Couldn't download the file"));
    } finally {
      setDownloading(null);
    }
  }

  async function pick(kind: AudioKind, e: ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    const problem = validateAudioFile(file);
    if (problem) {
      setUploadError(problem);
      return;
    }
    setUploadError(null);
    setUploading({ kind, name: file.name, fraction: 0 });
    const u = uploadAudio(episode.id, kind, file, (fraction) => setUploading((s) => (s ? { ...s, fraction } : s)));
    upload.current = u;
    try {
      const result = await u.promise;
      toast.push({
        kind: "success",
        title: `${kind === "final" ? "Final mix" : "Rough mix"} uploaded`,
        detail: `${file.name} (${fmtBytes(file.size)})${result.job_id ? " · transcription queued" : ""}.`,
      });
      refresh();
    } catch (err) {
      setUploadError(toApiError(err));
    } finally {
      upload.current = null;
      setUploading(null);
    }
  }

  if (error && !rows) {
    return (
      <Banner kind="error">
        <ErrorDetail error={error} lead="Couldn't list the audio." onRetry={refresh} />
      </Banner>
    );
  }

  return (
    <div className="audio">
      {KINDS.map(({ kind, label, hint }) => {
        const row = rows?.find((r) => r.kind === kind) ?? null;
        const known = rows === null ? "unknown" : row ? "present" : "absent";
        const busy = uploading?.kind === kind;
        return (
          <div key={kind} className={`audio-row audio-${known}`}>
            <span className={`signal signal-${known}`} aria-hidden="true">
              <i />
              <i />
              <i />
              <i />
            </span>
            <div className="audio-text">
              <strong>{label}</strong>
              {busy && uploading ? (
                <>
                  <span className="audio-meta">
                    Uploading {uploading.name}… {Math.round(uploading.fraction * 100)}%
                  </span>
                  <span className="progress" role="progressbar" aria-valuenow={Math.round(uploading.fraction * 100)} aria-valuemin={0} aria-valuemax={100}>
                    <i style={{ width: `${uploading.fraction * 100}%` }} />
                  </span>
                </>
              ) : row ? (
                <span className="audio-meta">
                  {row.filename ?? row.download_name}
                  {row.size_bytes ? ` · ${fmtBytes(row.size_bytes)}` : ""} · {who(row.uploaded_by)}, {fmtStamp(row.uploaded_at)}
                  {row.first_downloaded_at ? ` · picked up ${fmtStamp(row.first_downloaded_at)}` : " · not picked up yet"}
                </span>
              ) : (
                <span className="audio-meta">{rows === null ? hint : `Nothing uploaded yet. ${hint}`}</span>
              )}
              {uploadError && uploading === null && (
                <Banner kind="error">
                  <ErrorDetail error={uploadError} lead="The upload didn't go through." />
                </Banner>
              )}
            </div>
            <div className="audio-actions">
              {canUpload && (
                <>
                  <input
                    ref={(el) => {
                      inputs.current[kind] = el;
                    }}
                    type="file"
                    accept={AUDIO_ACCEPT}
                    hidden
                    onChange={(e) => void pick(kind, e)}
                  />
                  {busy ? (
                    <button type="button" className="btn btn-sm" onClick={() => upload.current?.abort()}>
                      Cancel
                    </button>
                  ) : (
                    <button
                      type="button"
                      className={`btn btn-sm${row ? "" : " btn-accent"}`}
                      disabled={uploading !== null}
                      onClick={() => inputs.current[kind]?.click()}
                    >
                      {row ? "Replace" : kind === "final" ? "Upload final mix" : "Upload"}
                    </button>
                  )}
                </>
              )}
              <button
                type="button"
                className={`btn btn-sm${row ? " btn-accent" : ""}`}
                disabled={downloading === kind || !row}
                onClick={() => void download(kind)}
              >
                {downloading === kind ? "Fetching…" : "Download"}
              </button>
            </div>
          </div>
        );
      })}
    </div>
  );
}
