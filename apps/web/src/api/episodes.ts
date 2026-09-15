import { API_BASE, api, detailOf, makeError, NETWORK_DETAIL } from "./client";
import { sha256 } from "../lib/audio";

export type Role = "audio_editor" | "video_editor" | "owner";

export type Stage =
  | "registered"
  | "mixing"
  | "plan_ready"
  | "editing"
  | "review"
  | "published"
  | "blocked";

export type ScheduleStatus = "on_track" | "due_soon" | "overdue" | "published";

export type AudioKind = "rough" | "final";

/** Exactly what GET /episodes returns. Note: no stage — see EpisodesProvider. */
export type EpisodeSummary = {
  id: string;
  title: string;
  recorded_on: string; // YYYY-MM-DD
  publish_on: string | null;
  days_remaining: number | null;
  schedule_status: ScheduleStatus | null;
};

export type Transition = {
  from: Stage;
  to: Stage;
  actor: string;
  role: Role;
  at: string;
  reason: string | null;
};

export const listEpisodes = () => api<EpisodeSummary[]>("/episodes");

export const createEpisode = (body: { title: string; recorded_on: string }) =>
  api<EpisodeSummary>("/episodes", { method: "POST", body: JSON.stringify(body) });

export const changeStage = (id: string, to_stage: Stage, reason: string | null) =>
  api<EpisodeSummary>(`/episodes/${id}/stage`, {
    method: "POST",
    body: JSON.stringify({ to_stage, reason }),
  });

export const setSlot = (id: string, publish_on: string) =>
  api<EpisodeSummary>(`/episodes/${id}/slot`, {
    method: "PUT",
    body: JSON.stringify({ publish_on }),
  });

export const getHistory = (id: string) => api<Transition[]>(`/episodes/${id}/history`);

export type UploadTarget = {
  url: string;
  method: "POST" | "PUT"; // POST: S3 presigned form. PUT: the local dev route.
  fields: Record<string, string>;
  headers: Record<string, string>;
  key: string;
  expires_in: number;
};

export type UploadResult = {
  audio_file_id: string;
  replayed: boolean;
  transcript_id: string | null;
  transcript_error: string | null; // the audio is stored either way
};

export type TranscriptSegment = { index: number; start_ms: number; end_ms: number; text: string };

export type Transcript = {
  id: string;
  audio_file_id: string;
  created_at: string;
  audio_checksum: string;
  engine: string;
  model_version: string;
  language: string;
  duration_ms: number;
  segments: TranscriptSegment[];
};

export const getTranscript = (id: string) => api<Transcript>(`/episodes/${id}/transcript`);

export const createUploadTarget = (
  id: string,
  body: { kind: AudioKind; filename: string; content_type: string; size_bytes: number },
) =>
  api<UploadTarget>(`/episodes/${id}/audio/upload-target`, {
    method: "POST",
    body: JSON.stringify(body),
  });

export const completeUpload = (id: string, body: { key: string; checksum_sha256: string }) =>
  api<UploadResult>(`/episodes/${id}/audio/complete`, {
    method: "POST",
    body: JSON.stringify(body),
  });

/** stamp=false fetches a URL for in-browser playback without counting as the handoff. */
export const getDownloadUrl = (id: string, kind: AudioKind, opts: { stamp?: boolean } = {}) =>
  api<{ url: string }>(`/episodes/${id}/audio/${kind}/download-url${opts.stamp === false ? "?stamp=false" : ""}`);

/** Local storage hands back a path on the API; S3 hands back an absolute URL. */
export const storageUrl = (url: string) => (url.startsWith("/") ? `${API_BASE}${url}` : url);

function storageError(xhr: XMLHttpRequest): string {
  // S3 answers with XML: <Error><Code>…</Code><Message>…</Message></Error>
  const msg = /<Message>([^<]*)<\/Message>/.exec(xhr.responseText)?.[1];
  if (msg) return msg;
  let body: unknown = null;
  try {
    body = JSON.parse(xhr.responseText);
  } catch {
    // not JSON; detailOf falls back to statusText
  }
  return detailOf(body, xhr.statusText || "Upload failed");
}

/**
 * The bytes go straight to storage, never through the API, so no bearer
 * header here. XMLHttpRequest rather than fetch so the progress bar is real.
 */
function transfer(
  xhr: XMLHttpRequest,
  target: UploadTarget,
  file: File,
  checksumBase64: string,
  onProgress?: (fraction: number) => void,
): Promise<void> {
  return new Promise((resolve, reject) => {
    xhr.open(target.method, storageUrl(target.url));
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onProgress?.(e.loaded / e.total);
    };
    xhr.onerror = () => reject(makeError(0, NETWORK_DETAIL, null));
    xhr.onabort = () => reject(makeError(0, "Upload cancelled.", null));
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) resolve();
      else reject(makeError(xhr.status, storageError(xhr), xhr.getResponseHeader("X-Trace-Id")));
    };
    if (target.method === "POST") {
      // Presigned POST: every signed field, the checksum, then the file LAST.
      const form = new FormData();
      for (const [name, value] of Object.entries(target.fields)) form.append(name, value);
      form.append("x-amz-checksum-sha256", checksumBase64);
      form.append("file", file);
      xhr.send(form);
    } else {
      for (const [name, value] of Object.entries(target.headers)) xhr.setRequestHeader(name, value);
      xhr.send(file);
    }
  });
}

export type Upload = { promise: Promise<UploadResult>; abort: () => void };

/** Hash, ask the API for a target, send the bytes to storage, tell the API. */
export function uploadAudio(
  id: string,
  kind: AudioKind,
  file: File,
  onProgress?: (fraction: number) => void,
): Upload {
  const xhr = new XMLHttpRequest();
  let cancelled = false;
  const cancelledError = () => makeError(0, "Upload cancelled.", null);
  const promise = (async () => {
    const checksum = await sha256(file);
    if (cancelled) throw cancelledError();
    const target = await createUploadTarget(id, {
      kind,
      filename: file.name,
      content_type: file.type || "application/octet-stream",
      size_bytes: file.size,
    });
    if (cancelled) throw cancelledError();
    await transfer(xhr, target, file, checksum.base64, onProgress);
    return completeUpload(id, { key: target.key, checksum_sha256: checksum.hex });
  })();
  return {
    promise,
    abort: () => {
      cancelled = true;
      xhr.abort();
    },
  };
}

/** The API hands back a presigned URL, so a plain link click does the transfer. */
export async function downloadAudio(id: string, kind: AudioKind): Promise<string> {
  const { url } = await getDownloadUrl(id, kind);
  const filename = `${kind}.wav`; // what the server puts in Content-Disposition
  const a = document.createElement("a");
  a.href = storageUrl(url);
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  return filename;
}
