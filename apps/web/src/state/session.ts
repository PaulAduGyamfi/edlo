import { createContext, useContext } from "react";

import { type Role } from "../api/episodes";

export type Identity = { name: string; role: Role };

export type SessionStatus = "checking" | "anonymous" | "signed_in";

export type SessionApi = {
  status: SessionStatus;
  me: Identity | null;
  /** Why the user is looking at the sign-in screen, if there is a reason. */
  notice: string | null;
  signIn: (token: string, identity: Identity) => Promise<void>;
  signOut: (notice?: string) => void;
};

export const SessionContext = createContext<SessionApi | null>(null);

export function useSession(): SessionApi {
  const ctx = useContext(SessionContext);
  if (!ctx) throw new Error("useSession must be used inside SessionProvider");
  return ctx;
}

/** The signed-in identity, for screens that only render once signed in. */
export function useMe(): Identity {
  const { me } = useSession();
  if (!me) throw new Error("useMe called while signed out");
  return me;
}

const IDENTITY_KEY = "edlo_identity";

export function loadIdentity(): Identity | null {
  try {
    const raw = localStorage.getItem(IDENTITY_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<Identity>;
    if (
      typeof parsed.name === "string" &&
      (parsed.role === "audio_editor" ||
        parsed.role === "video_editor" ||
        parsed.role === "owner")
    ) {
      return { name: parsed.name, role: parsed.role };
    }
    return null;
  } catch {
    return null;
  }
}

export function saveIdentity(identity: Identity | null): void {
  try {
    if (identity) localStorage.setItem(IDENTITY_KEY, JSON.stringify(identity));
    else localStorage.removeItem(IDENTITY_KEY);
  } catch {
    // storage unavailable; the session lasts until reload
  }
}
