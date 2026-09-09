import { type FormEvent, useState } from "react";

import { type ApiError, getToken, toApiError } from "../api/client";
import { type Role } from "../api/episodes";
import { ROLE_LABEL } from "../domain/workflow";
import { Banner } from "../components/Banner";
import { ErrorDetail } from "../components/ErrorDetail";
import { loadIdentity, useSession } from "../state/session";

import "../styles/app.css";

const ROLES: Role[] = ["audio_editor", "video_editor", "owner"];

// Dev only: the pilot tokens from apps/api/app/deps.py, so a local run is one click.
const DEV_PICKS: { name: string; role: Role; token: string }[] = import.meta.env.DEV
  ? [
      { name: "Albert", role: "audio_editor", token: "albert-token" },
      { name: "Chris", role: "video_editor", token: "chris-token" },
      { name: "Paul", role: "owner", token: "paul-token" },
    ]
  : [];

export function SignInScreen() {
  const { signIn, notice } = useSession();
  const remembered = loadIdentity();
  const [token, setToken] = useState(() => getToken() ?? "");
  const [name, setName] = useState(remembered?.name ?? "");
  const [role, setRole] = useState<Role>(remembered?.role ?? "audio_editor");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      await signIn(token.trim(), { name: name.trim(), role });
    } catch (err) {
      setError(toApiError(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="signin">
      <form className="signin-card" onSubmit={submit}>
        <span className="shell-mark signin-mark">EDLO</span>
        <h1 className="display-lg">Sign in</h1>
        <p className="signin-sub">
          Your pilot token identifies you to the server. Your name and role shape what this
          screen offers; the server still checks every move.
        </p>

        {notice && !error && <Banner kind="warn">{notice}</Banner>}

        <label className="field">
          <span>Pilot token</span>
          <input
            type="password"
            value={token}
            onChange={(e) => setToken(e.target.value)}
            autoComplete="current-password"
            required
          />
        </label>
        <div className="field-row">
          <label className="field">
            <span>Your name</span>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              autoComplete="name"
              required
              maxLength={60}
            />
          </label>
          <label className="field">
            <span>Role</span>
            <select value={role} onChange={(e) => setRole(e.target.value as Role)}>
              {ROLES.map((r) => (
                <option key={r} value={r}>
                  {ROLE_LABEL[r]}
                </option>
              ))}
            </select>
          </label>
        </div>

        {error && (
          <Banner kind="error">
            <ErrorDetail
              error={error}
              lead={error.status === 401 ? "That token was not accepted." : "Couldn't sign in."}
            />
          </Banner>
        )}

        <button
          type="submit"
          className="btn btn-accent btn-wide"
          disabled={busy || !token.trim() || !name.trim()}
        >
          {busy ? "Checking…" : "Sign in"}
        </button>

        {DEV_PICKS.length > 0 && (
          <div className="signin-dev">
            <span className="eyebrow">Dev shortcuts</span>
            <div className="signin-picks">
              {DEV_PICKS.map((p) => (
                <button
                  key={p.token}
                  type="button"
                  className="chip chip-btn"
                  onClick={() => {
                    setToken(p.token);
                    setName(p.name);
                    setRole(p.role);
                  }}
                >
                  {p.name} · {ROLE_LABEL[p.role]}
                </button>
              ))}
            </div>
          </div>
        )}
      </form>
    </main>
  );
}
