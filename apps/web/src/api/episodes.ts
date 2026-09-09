import {
  API_BASE,
  api,
  authHeaders,
  detailOf,
  getToken,
  handleResponse,
  makeError,
  NETWORK_DETAIL,
  notifyUnauthorized,
} from "./client";

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

export type UploadResult = {
  audio_file_id: string;
  size_bytes: number;
  checksum: string;
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

export type Upload = { promise: Promise<UploadResult>; abort: () => void };

/**
 * XMLHttpRequest rather than fetch so the progress bar is real. The browser
 * sets the multipart boundary, so no Content-Type header here.
 */
export function uploadAudio(
  id: string,
  kind: AudioKind,
  file: File,
  onProgress?: (fraction: number) => void,
): Upload {
  const xhr = new XMLHttpRequest();
  const promise = new Promise<UploadResult>((resolve, reject) => {
    xhr.open("POST", `${API_BASE}/episodes/${id}/audio?kind=${kind}`);
    const token = getToken();
    if (token) xhr.setRequestHeader("Authorization", `Bearer ${token}`);
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable) onProgress?.(e.loaded / e.total);
    };
    xhr.onerror = () => reject(makeError(0, NETWORK_DETAIL, null));
    xhr.onabort = () => reject(makeError(0, "Upload cancelled.", null));
    xhr.onload = () => {
      const traceId = xhr.getResponseHeader("X-Trace-Id");
      let body: unknown = null;
      try {
        body = JSON.parse(xhr.responseText);
      } catch {
        // non-JSON error page; detailOf falls back to statusText
      }
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(body as UploadResult);
      } else {
        if (xhr.status === 401) notifyUnauthorized();
        reject(
          makeError(
            xhr.status,
            detailOf(body, xhr.statusText || "Upload failed"),
            traceId,
          ),
        );
      }
    };
    const form = new FormData();
    form.append("file", file);
    xhr.send(form);
  });
  return { promise, abort: () => xhr.abort() };
}

/**
 * The download needs the bearer header, so a plain <a href> won't do: fetch
 * the bytes, then hand them to the browser as a file.
 */
export async function downloadAudio(id: string, kind: AudioKind): Promise<string> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE}/episodes/${id}/audio/${kind}`, {
      headers: authHeaders(),
    });
  } catch {
    throw makeError(0, NETWORK_DETAIL, null);
  }
  if (!res.ok) await handleResponse<never>(res); // throws

  const blob = await res.blob();
  const disposition = res.headers.get("Content-Disposition") ?? "";
  const match = /filename="([^"]+)"/.exec(disposition);
  const filename = match?.[1] ?? `${kind}-${id.slice(0, 8)}.wav`;

  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
  return filename;
}
