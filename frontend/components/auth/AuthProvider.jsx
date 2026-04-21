"use client";

import { createContext, useContext, useEffect, useMemo, useState } from "react";

const AuthContext = createContext(null);
const STORAGE_KEY = "xynera.auth";
const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";


function normalizeApiError(err, fallbackMessage) {
  if (err instanceof Error) {
    return err.message;
  }

  if (typeof err === "string") {
    return err;
  }

  return fallbackMessage;
}


async function postJson(path, body, accessToken) {
  const response = await fetch(`${API_URL}${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
    },
    body: JSON.stringify(body),
  });

  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.detail || "Request failed");
  }

  return payload;
}


async function getJson(path, accessToken) {
  const response = await fetch(`${API_URL}${path}`, {
    method: "GET",
    headers: {
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
    },
  });

  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.detail || "Request failed");
  }

  return payload;
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [accessToken, setAccessToken] = useState(null);
  const [refreshToken, setRefreshToken] = useState(null);
  const [ready, setReady] = useState(false);

  function clearAuthState() {
    window.localStorage.removeItem(STORAGE_KEY);
    setUser(null);
    setAccessToken(null);
    setRefreshToken(null);
  }

  function persistAuthState(nextState) {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(nextState));
    setUser(nextState.user || null);
    setAccessToken(nextState.accessToken || null);
    setRefreshToken(nextState.refreshToken || null);
  }

  useEffect(() => {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (raw) {
      try {
        const data = JSON.parse(raw);
        if (data?.accessToken) {
          persistAuthState({
            user: data.user || null,
            accessToken: data.accessToken || null,
            refreshToken: data.refreshToken || null,
          });
        }
      } catch {
        window.localStorage.removeItem(STORAGE_KEY);
      }
    }
    setReady(true);
  }, []);

  const value = useMemo(() => {
    return {
      user,
      accessToken,
      refreshToken,
      ready,
      isAuthenticated: Boolean(user),
      refreshAccessToken: async () => {
        if (!refreshToken) {
          throw new Error("Missing refresh token");
        }

        try {
          const payload = await postJson("/auth/refresh", { refresh_token: refreshToken });
          const nextState = {
            user,
            accessToken: payload.access_token,
            refreshToken: payload.refresh_token || refreshToken,
          };
          persistAuthState(nextState);
          return nextState.accessToken;
        } catch (err) {
          clearAuthState();
          throw new Error(normalizeApiError(err, "Session expired. Please sign in again."));
        }
      },
      apiGet: async (path) => {
        if (!accessToken) {
          throw new Error("Missing access token");
        }

        try {
          return await getJson(path, accessToken);
        } catch (err) {
          const message = normalizeApiError(err, "Request failed");
          if (message.toLowerCase().includes("invalid or expired token") && refreshToken) {
            const payload = await postJson("/auth/refresh", { refresh_token: refreshToken });
            const nextState = {
              user,
              accessToken: payload.access_token,
              refreshToken: payload.refresh_token || refreshToken,
            };
            persistAuthState(nextState);
            return await getJson(path, nextState.accessToken);
          }
          throw new Error(message);
        }
      },
      apiPost: async (path, body) => {
        if (!accessToken) {
          throw new Error("Missing access token");
        }

        try {
          return await postJson(path, body, accessToken);
        } catch (err) {
          const message = normalizeApiError(err, "Request failed");
          if (message.toLowerCase().includes("invalid or expired token") && refreshToken) {
            const payload = await postJson("/auth/refresh", { refresh_token: refreshToken });
            const nextState = {
              user,
              accessToken: payload.access_token,
              refreshToken: payload.refresh_token || refreshToken,
            };
            persistAuthState(nextState);
            return await postJson(path, body, nextState.accessToken);
          }
          throw new Error(message);
        }
      },
      login: async (email, password) => {
        if (!email || !password) {
          throw new Error("Email and password are required.");
        }

        try {
          const payload = await postJson("/auth/login", { email, password });
          const state = {
            user: payload.user,
            accessToken: payload.access_token,
            refreshToken: payload.refresh_token,
          };
          persistAuthState(state);
        } catch (err) {
          throw new Error(normalizeApiError(err, "Login failed."));
        }
      },
      loginWithGoogle: async (idToken) => {
        if (!idToken) {
          throw new Error("Google token is required.");
        }

        try {
          const payload = await postJson("/auth/google", { id_token: idToken });
          const state = {
            user: payload.user,
            accessToken: payload.access_token,
            refreshToken: payload.refresh_token,
          };
          persistAuthState(state);
        } catch (err) {
          throw new Error(normalizeApiError(err, "Google login failed."));
        }
      },
      register: async (name, email, password) => {
        if (!name || !email || !password) {
          throw new Error("All fields are required.");
        }

        try {
          const payload = await postJson("/auth/register", { name, email, password });
          const state = {
            user: payload.user,
            accessToken: payload.access_token,
            refreshToken: payload.refresh_token,
          };
          persistAuthState(state);
        } catch (err) {
          throw new Error(normalizeApiError(err, "Registration failed."));
        }
      },
      refreshCurrentUser: async () => {
        if (!accessToken) {
          return;
        }

        const payload = await getJson("/auth/me", accessToken);
        const state = {
          user: payload.user,
          accessToken,
          refreshToken,
        };
        persistAuthState(state);
      },
      logout: () => {
        clearAuthState();
      },
    };
  }, [accessToken, refreshToken, user, ready]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return context;
}
