import { API_BASE, api, authHeaders, detailOf, handleResponse, makeError, NETWORK_DETAIL } from "./client";
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

/** 204. Removes the audio, transcript, jobs, history and posting slot with it. */
export const deleteEpisode = (id: string) => api<void>(`/episodes/${id}`, { method: "DELETE" });

export type UploadTarget = {
  url: string;
  method: "POST" | "PUT"; // POST: S3 presigned form. PUT: the local dev route.
  fields: Record<string, string>;
  headers: Record<string, string>;
  key: string;
  expires_in: number;
};

/** 202: the bytes are verified and a transcription job is queued. */
export type UploadResult = {
  audio_file_id: string;
  replayed: boolean;
  job_id: string | null; // the transcription job for a rough mix; null for a final mix
  poll_url: string | null;
};

export type AudioRow = {
  kind: AudioKind;
  audio_file_id: string;
  filename: string | null;
  download_name: string;
  size_bytes: number | null;
  uploaded_by: string;
  uploaded_at: string;
  first_downloaded_at: string | null;
};

export const listAudio = (id: string) => api<AudioRow[]>(`/episodes/${id}/audio`);

export type JobStatus = "queued" | "running" | "succeeded" | "failed" | "dead";

export type JobView = {
  id: string;
  kind: string;
  episode_id: string;
  status: JobStatus;
  attempt: number;
  error_class: string | null;
  user_message: string | null; // only for dead jobs
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  worker: string | null;
  progress: {
    stage?: string;
    windows_done?: number;
    windows?: number;
    audio_done_ms?: number; // transcription: how much of the audio is done
    audio_ms?: number;
  } | null;
  queue_position: number | null;
};

export const getJob = (id: string) => api<JobView>(`/jobs/${id}`);

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

/** 200 with the transcript, or 202 while its job is queued, running or dead. */
export type TranscriptResponse = Transcript | { status: "pending"; job: JobView };

export const getTranscript = (id: string) => api<TranscriptResponse>(`/episodes/${id}/transcript`);

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
    // One key per upload, reused by any retry of this same complete call, so
    // a retry gets the original answer instead of a second job.
    headers: { "Idempotency-Key": body.key },
  });

/** stamp=false fetches a URL for in-browser playback without counting as the handoff. */
export const getDownloadUrl = (id: string, kind: AudioKind, opts: { stamp?: boolean } = {}) =>
  api<{ url: string; filename: string }>(
    `/episodes/${id}/audio/${kind}/download-url${opts.stamp === false ? "?stamp=false" : ""}`,
  );

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
  const { url, filename } = await getDownloadUrl(id, kind); // the name it was uploaded as
  const a = document.createElement("a");
  a.href = storageUrl(url);
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  return filename;
}

// ---- flags, plans, packs (chapters 20 and 22)

export type Flag = {
  id: string;
  start_ms: number;
  end_ms: number;
  note: string | null;
  created_by: string;
  created_at: string;
};

export const listFlags = (id: string) => api<Flag[]>(`/episodes/${id}/flags`);

export const addFlag = (id: string, body: { start_ms: number; end_ms: number; note?: string | null }) =>
  api<Flag>(`/episodes/${id}/flags`, { method: "POST", body: JSON.stringify(body) });

export const deleteFlag = (id: string, flagId: string) =>
  api<void>(`/episodes/${id}/flags/${flagId}`, { method: "DELETE" });

export type Decision = "pending" | "accepted" | "rejected";

export type CutItemView = {
  id: string;
  source: "human" | "model";
  flag_id: string | null;
  position: number;
  start_ms: number;
  end_ms: number;
  edited_start_ms: number | null;
  edited_end_ms: number | null;
  quote: string;
  reason: string | null;
  confidence: number | null;
  decision: Decision;
};

export type ColdOpenView = {
  id: string;
  position: number;
  start_ms: number;
  end_ms: number;
  quote: string;
  why: string | null;
  confidence: number | null;
  picked: boolean;
};

export type StepView = { id: string; position: number; label: string; done_at: string | null };

export type PlanView = {
  id: string;
  status: "ready" | "ai_disabled";
  prompt_version: string;
  model: string;
  windows: number;
  proposed: number;
  rejections: Record<string, number>;
  generated_at: string;
  items: CutItemView[];
  cold_opens: ColdOpenView[];
  steps: StepView[];
};

export type PlanResponse = PlanView | { status: "pending"; job: JobView };

export const getPlan = (id: string) => api<PlanResponse>(`/episodes/${id}/plan`);

/** One key per click: a retry of the same click replays, a new click regenerates. */
export const generatePlan = (id: string) =>
  api<{ job_id: string; poll_url: string; ai_enabled: boolean }>(`/episodes/${id}/plan`, {
    method: "POST",
    headers: { "Idempotency-Key": crypto.randomUUID() },
  });

export const decideCut = (
  id: string,
  itemId: string,
  body: { decision?: Decision; start_ms?: number; end_ms?: number },
) => api<CutItemView>(`/episodes/${id}/plan/items/${itemId}`, { method: "POST", body: JSON.stringify(body) });

export const pickColdOpen = (id: string, coldId: string, picked: boolean) =>
  api<ColdOpenView>(`/episodes/${id}/plan/cold-opens/${coldId}`, {
    method: "POST",
    body: JSON.stringify({ picked }),
  });

export const tickStep = (id: string, stepId: string, done: boolean) =>
  api<StepView>(`/episodes/${id}/plan/steps/${stepId}`, { method: "POST", body: JSON.stringify({ done }) });

export async function getPlanExport(id: string): Promise<string> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/episodes/${id}/plan/export`, { headers: authHeaders() });
  } catch {
    throw makeError(0, NETWORK_DETAIL, null);
  }
  if (!res.ok) await handleResponse<never>(res); // throws
  return res.text();
}

export type Violation = { rule: string; detail: string };

export type PackView = {
  id: string;
  status: "ready" | "ai_disabled";
  prompt_version: string;
  model: string;
  title: string;
  description: string;
  chapters: { start_ms: number; title: string }[];
  links: string[];
  sponsors: string[];
  violations: Violation[];
  generated_at: string;
};

export type PackResponse = PackView | { status: "pending"; job: JobView };

export const getPack = (id: string) => api<PackResponse>(`/episodes/${id}/pack`);

export const generatePack = (id: string) =>
  api<{ job_id: string; poll_url: string; ai_enabled: boolean }>(`/episodes/${id}/pack`, {
    method: "POST",
    headers: { "Idempotency-Key": crypto.randomUUID() },
  });

export const approveEpisode = (id: string) =>
  api<{ id: string; stage: Stage; published_at: string }>(`/episodes/${id}/approve`, { method: "POST" });
