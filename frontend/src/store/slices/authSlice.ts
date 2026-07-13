import { createSlice } from "@reduxjs/toolkit";
import type { PayloadAction } from "@reduxjs/toolkit";
import type { User } from "../types";
import { authApi } from "../api/authApi";

// ── Persistence helpers ───────────────────────────────────────────────────────

const KEYS = {
  user: "chat_user",
  accessToken: "chat_access_token",
  refreshToken: "chat_refresh_token",
} as const;

function persist(user: User, access: string, refresh: string) {
  localStorage.setItem(KEYS.user, JSON.stringify(user));
  localStorage.setItem(KEYS.accessToken, access);
  localStorage.setItem(KEYS.refreshToken, refresh);
}

function clearPersisted() {
  Object.values(KEYS).forEach((k) => localStorage.removeItem(k));
}

// ── State ─────────────────────────────────────────────────────────────────────

interface AuthState {
  user: User | null;
  accessToken: string | null;
  refreshToken: string | null;
}

const initialState: AuthState = {
  // Rehydrate from localStorage on every page load
  user: (() => {
    try {
      const raw = localStorage.getItem(KEYS.user);
      return raw ? (JSON.parse(raw) as User) : null;
    } catch {
      return null;
    }
  })(),
  accessToken: localStorage.getItem(KEYS.accessToken),
  refreshToken: localStorage.getItem(KEYS.refreshToken),
};

// ── Slice ─────────────────────────────────────────────────────────────────────

const authSlice = createSlice({
  name: "auth",
  initialState,
  reducers: {
    /**
     * Manually set credentials — use this when you need to set tokens from
     * outside RTK Query (e.g. from a WebSocket auth flow).
     */
    setCredentials(
      state,
      action: PayloadAction<{
        user: User;
        accessToken: string;
        refreshToken: string;
      }>
    ) {
      const { user, accessToken, refreshToken } = action.payload;
      state.user = user;
      state.accessToken = accessToken;
      state.refreshToken = refreshToken;
      persist(user, accessToken, refreshToken);
    },

    /**
     * Clear everything — use on logout or on 401 errors.
     */
    clearCredentials(state) {
      state.user = null;
      state.accessToken = null;
      state.refreshToken = null;
      clearPersisted();
    },
  },

  /**
   * Auto-sync state + localStorage whenever RTK Query auth mutations succeed.
   * No need to call dispatch(setCredentials(...)) in components.
   */
  extraReducers: (builder) => {
    builder
      // Login
      .addMatcher(
        authApi.endpoints.login.matchFulfilled,
        (state, { payload }) => {
          state.user = payload.user;
          state.accessToken = payload.access_token;
          state.refreshToken = payload.refresh_token;
          persist(payload.user, payload.access_token, payload.refresh_token);
        }
      )
      // Register
      .addMatcher(
        authApi.endpoints.register.matchFulfilled,
        (state, { payload }) => {
          state.user = payload.user;
          state.accessToken = payload.access_token;
          state.refreshToken = payload.refresh_token;
          persist(payload.user, payload.access_token, payload.refresh_token);
        }
      )
      // Token refresh — only tokens change, user stays the same
      .addMatcher(
        authApi.endpoints.refreshToken.matchFulfilled,
        (state, { payload }) => {
          state.accessToken = payload.access_token;
          state.refreshToken = payload.refresh_token;
          localStorage.setItem(KEYS.accessToken, payload.access_token);
          localStorage.setItem(KEYS.refreshToken, payload.refresh_token);
        }
      )
      // Logout — wipe everything
      .addMatcher(authApi.endpoints.logout.matchFulfilled, (state) => {
        state.user = null;
        state.accessToken = null;
        state.refreshToken = null;
        clearPersisted();
      })
      // Profile update — keep token, refresh user object
      .addMatcher(
        authApi.endpoints.updateMe.matchFulfilled,
        (state, { payload }) => {
          state.user = payload;
          localStorage.setItem(KEYS.user, JSON.stringify(payload));
        }
      );
  },
});

export const { setCredentials, clearCredentials } = authSlice.actions;
export default authSlice.reducer;

// ── Selectors ─────────────────────────────────────────────────────────────────
export const selectCurrentUser = (state: { auth: AuthState }) => state.auth.user;
export const selectAccessToken = (state: { auth: AuthState }) => state.auth.accessToken;
export const selectRefreshToken = (state: { auth: AuthState }) => state.auth.refreshToken;
export const selectIsAuthenticated = (state: { auth: AuthState }) =>
  state.auth.accessToken !== null && state.auth.user !== null;
