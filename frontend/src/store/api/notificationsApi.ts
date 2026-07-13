import { baseApi } from "./baseApi";
import type { NotificationListResponse, Notification } from "../types";

export const notificationsApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    // ── GET /notifications ────────────────────────────────────────────────────
    getNotifications: build.query<NotificationListResponse, void>({
      query: () => "/notifications",
      providesTags: ["Notification"],
    }),

    // ── PUT /notifications/{id}/read ──────────────────────────────────────────
    markNotificationRead: build.mutation<Notification, string>({
      query: (notificationId) => ({
        url: `/notifications/${notificationId}/read`,
        method: "PUT",
      }),
      invalidatesTags: ["Notification"],
    }),

    // ── PUT /notifications/read-all ───────────────────────────────────────────
    markAllNotificationsRead: build.mutation<{ marked_read: number }, void>({
      query: () => ({
        url: "/notifications/read-all",
        method: "PUT",
      }),
      invalidatesTags: ["Notification"],
    }),
  }),
  overrideExisting: false,
});

export const {
  useGetNotificationsQuery,
  useMarkNotificationReadMutation,
  useMarkAllNotificationsReadMutation,
} = notificationsApi;
