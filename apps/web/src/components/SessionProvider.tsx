import { type ReactNode, useCallback, useEffect, useMemo, useState } from "react";

import { clearToken, getToken, isApiError, onUnauthorized, setToken } from "../api/client";
import { getHistory } from "../api/episodes";
import {
  type Identity,
  loadIdentity,
  saveIdentity,
  SessionContext,
  type SessionStatus,
} from "../state/session";

type State = { status: SessionStatus; me: Identity | null; notice: string | null };

const REJECTED = "That token was not accepted. Check it and sign in again.";

/**
 * There is no "who am I" endpoint, so a token is validated by making the
 * cheapest call that actually checks it: the history route requires a bearer
 * token and answers an empty list for an unknown id (the list route is open).
 * The identity (name and role) is the user's own claim, kept locally; the
 * server still enforces permissions on every write.
 */
const checkToken = () => getHistory("token-check");
export function SessionProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<State>(() => {
    const identity = loadIdentity();
    return getToken() && identity
      ? { status: "checking", me: identity, notice: null }
      : { status: "anonymous", me: null, notice: null };
  });

  const signOut = useCallback((notice?: string) => {
    clearToken();
    saveIdentity(null);
    setState({ status: "anonymous", me: null, notice: notice ?? null });
  }, []);

  const signIn = useCallback(async (token: string, identity: Identity) => {
    setToken(token);
    try {
      await checkToken();
    } catch (e) {
      if (isApiError(e) && e.status === 401) clearToken();
      throw e;
    }
    saveIdentity(identity);
    setState({ status: "signed_in", me: identity, notice: null });
  }, []);

  // Re-validate a remembered token on load.
  useEffect(() => {
    if (state.status !== "checking") return;
    let cancelled = false;
    checkToken().then(
      () => {
        if (!cancelled) setState((s) => ({ ...s, status: "signed_in" }));
      },
      (e: unknown) => {
        if (cancelled) return;
        if (isApiError(e) && e.status === 401) {
          clearToken();
          setState({ status: "anonymous", me: null, notice: REJECTED });
        } else {
          // Server unreachable: keep the token so a retry from the sign-in
          // screen is one click.
          const detail = isApiError(e) ? e.detail : "Could not check your session.";
          setState((s) => ({ status: "anonymous", me: s.me, notice: detail }));
        }
      },
    );
    return () => {
      cancelled = true;
    };
  }, [state.status]);

  useEffect(() => {
    onUnauthorized(() => signOut("Your session was rejected by the server. Sign in again."));
    return () => onUnauthorized(null);
  }, [signOut]);

  const value = useMemo(
    () => ({ ...state, signIn, signOut }),
    [state, signIn, signOut],
  );

  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}
