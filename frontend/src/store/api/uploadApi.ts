import { baseApi } from "./baseApi";
import type { UploadResponse } from "../types";

export const uploadApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    // ── POST /upload ──────────────────────────────────────────────────────────
    uploadFile: build.mutation<UploadResponse, FormData>({
      query: (formData) => ({
        url: "/upload",
        method: "POST",
        body: formData,
        /**
         * Do NOT set Content-Type manually.
         * The browser sets it automatically with the correct multipart boundary.
         * RTK Query's fetchBaseQuery does not set Content-Type for FormData
         * if you pass formData: true.
         */
        formData: true,
      }),
    }),
  }),
  overrideExisting: false,
});

export const { useUploadFileMutation } = uploadApi;
