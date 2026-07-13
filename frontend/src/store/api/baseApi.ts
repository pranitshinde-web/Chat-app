import { createApi, fetchBaseQuery } from "@reduxjs/toolkit/query/react";
import type { RootState } from "../index";

export const BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8001";

/**
 * Single RTK Query base instance.
 * All feature APIs are injected into this via injectEndpoints().
 * The middleware and reducer are registered in the store.
 */
export const baseApi = createApi({
  reducerPath: "api",

  baseQuery: fetchBaseQuery({
    baseUrl: `${BASE_URL}/api`,
    /**
     * Attach the access token from Redux state to every outgoing request.
     * This runs before every query and mutation, so no per-hook boilerplate.
     */
    prepareHeaders: (headers, { getState }) => {
      const token = (getState() as RootState).auth.accessToken;
      if (token) {
        headers.set("Authorization", `Bearer ${token}`);
      }
      return headers;
    },
  }),

  /**
   * Tag types used for cache invalidation across all injected endpoints.
   * Add new tags here as features grow.
   */
  tagTypes: ["User", "Room", "Message", "Notification"],

  // Endpoints are injected per-feature file; this stays empty.
  endpoints: () => ({}),
});
