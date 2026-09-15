import { type ApiError } from "../api/client";

export const AUDIO_ACCEPT = ".wav,.mp3,.m4a,.aiff,.flac";
const ALLOWED = new Set(["wav", "mp3", "m4a", "aiff", "flac"]);
// Matches max_upload_bytes on the server.
export const AUDIO_MAX_BYTES = 500 * 1024 * 1024;

export function fmtBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  const units = ["KB", "MB", "GB"];
  let v = n / 1024;
  let i = 0;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i++;
  }
  return `${v < 10 ? v.toFixed(1) : Math.round(v)} ${units[i]}`;
}

/** Same checks the server makes, so a bad file is refused before any bytes move. */
export function validateAudioFile(file: File): ApiError | null {
  const ext = file.name.split(".").pop()?.toLowerCase() ?? "";
  if (!ALLOWED.has(ext)) {
    return {
      name: "ApiError",
      status: 415,
      detail: `“.${ext}” is not an accepted audio format. Use ${AUDIO_ACCEPT.replaceAll(",", ", ")}.`,
      traceId: null,
      retryable: false,
    };
  }
  if (file.size > AUDIO_MAX_BYTES) {
    return {
      name: "ApiError",
      status: 413,
      detail: `${file.name} is ${fmtBytes(file.size)}; the limit is ${fmtBytes(AUDIO_MAX_BYTES)}.`,
      traceId: null,
      retryable: false,
    };
  }
  return null;
}

/** SHA-256 of the whole file: hex for the API's complete call, base64 for S3's checksum field. */
export async function sha256(file: File): Promise<{ hex: string; base64: string }> {
  const digest = new Uint8Array(await crypto.subtle.digest("SHA-256", await file.arrayBuffer()));
  const hex = Array.from(digest, (b) => b.toString(16).padStart(2, "0")).join("");
  const base64 = btoa(String.fromCharCode(...digest));
  return { hex, base64 };
}
