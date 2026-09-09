import { type ChangeEvent, type FormEvent, useEffect, useRef, useState } from "react";

import { type ApiError, toApiError } from "../api/client";
import { createEpisode, type EpisodeSummary, setSlot, type Upload, uploadAudio } from "../api/episodes";
import { AUDIO_ACCEPT, AUDIO_MAX_BYTES, fmtBytes, validateAudioFile } from "../lib/audio";
import { fmtDate, fmtDateLong, todayISO } from "../lib/dates";
import { useEpisodes } from "../state/episodes";
import { useToast } from "../state/toast";
import { Banner } from "./Banner";
import { Dialog } from "./Dialog";
import { ErrorDetail } from "./ErrorDetail";

type Phase =
  | { step: "form" }
  | { step: "creating" }
  | { step: "uploading"; episode: EpisodeSummary; fraction: number }
  | { step: "upload_failed"; episode: EpisodeSummary; error: ApiError };

/**
 * Registering an episode is handing in the recording: title, date, the
 * rough mix. The episode is created first, then the file goes up against
 * it, so a failed upload leaves a registered episode that can be retried.
 */
export function RegisterEpisodeDialog({
  publishOn = null,
  onClose,
  onCreated,
}: {
  /** Preset posting date, when registering from a free slot on the schedule. */
  publishOn?: string | null;
  onClose: () => void;
  onCreated: (episode: EpisodeSummary) => void;
}) {
  const [title, setTitle] = useState("");
  const [recordedOn, setRecordedOn] = useState(todayISO);
  const [file, setFile] = useState<File | null>(null);
  const [fileError, setFileError] = useState<ApiError | null>(null);
  const [phase, setPhase] = useState<Phase>({ step: "form" });
  const [error, setError] = useState<ApiError | null>(null);
  const upload = useRef<Upload | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const { patch } = useEpisodes();
  const toast = useToast();

  useEffect(() => () => upload.current?.abort(), []);

  const busy = phase.step === "creating" || phase.step === "uploading";

  function onPick(e: ChangeEvent<HTMLInputElement>) {
    const picked = e.target.files?.[0] ?? null;
    if (!picked) return;
    const problem = validateAudioFile(picked);
    setFileError(problem);
    setFile(problem ? null : picked);
    if (problem) e.target.value = "";
  }

  async function sendFile(episode: EpisodeSummary) {
    if (!file) return;
    setPhase({ step: "uploading", episode, fraction: 0 });
    const u = uploadAudio(episode.id, "rough", file, (fraction) =>
      setPhase((p) => (p.step === "uploading" ? { ...p, fraction } : p)),
    );
    upload.current = u;
    try {
      const result = await u.promise;
      toast.push({
        kind: "success",
        title: `Registered “${episode.title}”`,
        detail: `${file.name} (${fmtBytes(result.size_bytes)}) uploaded${episode.publish_on ? ` · posting slot ${fmtDate(episode.publish_on)}` : ""}.`,
      });
      onCreated(episode);
    } catch (err) {
      setPhase({ step: "upload_failed", episode, error: toApiError(err) });
    } finally {
      upload.current = null;
    }
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (busy || !file) return;
    setPhase({ step: "creating" });
    setError(null);
    let created: EpisodeSummary;
    try {
      created = await createEpisode({ title: title.trim(), recorded_on: recordedOn });
      patch(created, { stage: "registered", history: [], historyError: null });
    } catch (err) {
      setError(toApiError(err));
      setPhase({ step: "form" });
      return;
    }
    // A chosen date is a second step; the episode exists either way.
    if (publishOn && publishOn !== created.publish_on) {
      try {
        created = await setSlot(created.id, publishOn);
        patch(created);
      } catch (slotErr) {
        const err = toApiError(slotErr);
        toast.push({
          kind: "error",
          title: `Couldn't take ${fmtDate(publishOn)}`,
          detail: `${err.detail} The episode has ${created.publish_on ? fmtDate(created.publish_on) : "no date"} instead.`,
          traceId: err.traceId,
        });
      }
    }
    await sendFile(created);
  }

  if (phase.step === "uploading" || phase.step === "upload_failed") {
    const pct = phase.step === "uploading" ? Math.round(phase.fraction * 100) : 100;
    return (
      <Dialog title="Register episode" onClose={() => phase.step === "upload_failed" && onClose()}>
        <div className="form">
          <p className="form-hint">
            <strong>{phase.episode.title}</strong> is registered
            {phase.episode.publish_on ? ` for ${fmtDateLong(phase.episode.publish_on)}` : ""}.
          </p>
          <div className="upload-status">
            <span className="upload-name">{file?.name}</span>
            <span className="upload-meta">
              {phase.step === "uploading" ? `Uploading rough mix… ${pct}%` : "Upload failed."}
            </span>
            <span className="progress" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}>
              <i style={{ width: `${pct}%` }} />
            </span>
          </div>
          {phase.step === "upload_failed" && (
            <Banner kind="error">
              <ErrorDetail error={phase.error} lead="The recording didn't reach the server." />
            </Banner>
          )}
          <div className="form-actions">
            {phase.step === "uploading" ? (
              <button type="button" className="btn" onClick={() => upload.current?.abort()}>
                Cancel upload
              </button>
            ) : (
              <>
                <button type="button" className="link" onClick={() => onCreated(phase.episode)}>
                  Skip for now
                </button>
                <button type="button" className="btn btn-accent" onClick={() => void sendFile(phase.episode)}>
                  Retry upload
                </button>
              </>
            )}
          </div>
        </div>
      </Dialog>
    );
  }

  return (
    <Dialog title="Register episode" onClose={onClose}>
      <form className="form" onSubmit={submit}>
        <p className="form-hint">
          {publishOn
            ? `Posting slot: ${fmtDateLong(publishOn)}. The countdown starts now.`
            : "Registering hands in the recording and takes the next free posting slot, two weeks after the recording date."}
        </p>
        <label className="field">
          <span>Title</span>
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            maxLength={300}
            required
            placeholder="e.g. The Landlord Question"
            autoComplete="off"
          />
        </label>
        <label className="field">
          <span>Recorded on</span>
          <input type="date" value={recordedOn} onChange={(e) => setRecordedOn(e.target.value)} required />
        </label>
        <div className="field">
          <span>Recording (rough mix)</span>
          <input ref={fileInput} type="file" accept={AUDIO_ACCEPT} hidden onChange={onPick} />
          <div className={`filepick${file ? " filepick-on" : ""}`}>
            <button type="button" className="btn btn-sm" onClick={() => fileInput.current?.click()}>
              {file ? "Change file" : "Choose file"}
            </button>
            <span className="filepick-name">
              {file ? `${file.name} · ${fmtBytes(file.size)}` : `${AUDIO_ACCEPT.replaceAll(",", " ")} · up to ${fmtBytes(AUDIO_MAX_BYTES)}`}
            </span>
          </div>
          {fileError && (
            <Banner kind="error">
              <ErrorDetail error={fileError} />
            </Banner>
          )}
        </div>
        {error && (
          <Banner kind="error">
            <ErrorDetail error={error} lead="Couldn't register the episode." />
          </Banner>
        )}
        <div className="form-actions">
          <button type="button" className="btn" onClick={onClose} disabled={busy}>
            Cancel
          </button>
          <button
            type="submit"
            className="btn btn-accent"
            disabled={busy || title.trim().length === 0 || !recordedOn || !file}
            title={file ? undefined : "Choose the recording first."}
          >
            {phase.step === "creating" ? "Registering…" : "Register and upload"}
          </button>
        </div>
      </form>
    </Dialog>
  );
}
