import { baseApi } from "./baseApi";
import type { AuthResponse, Token, User } from "../types";

export const authApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    // ── POST /auth/register ─────────────────────────────────────────────────
    register: build.mutation<
      AuthResponse,
      { username: string; email: string; password: string }
    >({
      query: (body) => ({
        url: "/auth/register",
        method: "POST",
        body,
      }),
    }),

    // ── POST /auth/login ────────────────────────────────────────────────────
    login: build.mutation<AuthResponse, { email: string; password: string }>({
      query: (body) => ({
        url: "/auth/login",
        method: "POST",
        body,
      }),
    }),

    // ── POST /auth/refresh ──────────────────────────────────────────────────
    refreshToken: build.mutation<Token, { refresh_token: string }>({
      query: (body) => ({
        url: "/auth/refresh",
        method: "POST",
        body,
      }),
    }),

    // ── POST /auth/logout ───────────────────────────────────────────────────
    logout: build.mutation<void, { refresh_token: string }>({
      query: (body) => ({
        url: "/auth/logout",
        method: "POST",
        body,
      }),
    }),

    // ── GET /users/me ───────────────────────────────────────────────────────
    getMe: build.query<User, void>({
      query: () => "/users/me",
      providesTags: ["User"],
    }),

    // ── PUT /users/me ───────────────────────────────────────────────────────
    updateMe: build.mutation<User, { username?: string; avatar_url?: string }>({
      query: (body) => ({
        url: "/users/me",
        method: "PUT",
        body,
      }),
      invalidatesTags: ["User"],
    }),
  }),
  overrideExisting: false,
});

export const {
  useRegisterMutation,
  useLoginMutation,
  useRefreshTokenMutation,
  useLogoutMutation,
  useGetMeQuery,
  useUpdateMeMutation,
} = authApi;
