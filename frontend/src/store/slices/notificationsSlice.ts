import { createSlice } from "@reduxjs/toolkit";
import type { PayloadAction } from "@reduxjs/toolkit";
import type { Notification } from "../types";
import { notificationsApi } from "../api/notificationsApi";

// ── State ─────────────────────────────────────────────────────────────────────

interface NotificationsState {
  /**
   * Unread notifications injected by the WebSocket notifications.pending event
   * immediately on connect. Also updated optimistically when the user marks
   * notifications as read.
   */
  items: Notification[];
}

const initialState: NotificationsState = {
  items: [],
};

// ── Slice ─────────────────────────────────────────────────────────────────────

const notificationsSlice = createSlice({
  name: "notifications",
  initialState,
  reducers: {
    /**
     * Replace the entire list — called when the WebSocket delivers a
     * notifications.pending event on connect.
     */
    setPendingNotifications(state, action: PayloadAction<Notification[]>) {
      state.items = action.payload;
    },

    /**
     * Append a single notification received live (e.g. real-time mention).
     * Deduplicates by _id.
     */
    addNotification(state, action: PayloadAction<Notification>) {
      const exists = state.items.some((n) => n._id === action.payload._id);
      if (!exists) {
        state.items.unshift(action.payload); // newest first
      }
    },

    clearAllNotifications(state) {
      state.items = [];
    },
  },

  extraReducers: (builder) => {
    builder
      // After marking one read — remove from local list
      .addMatcher(
        notificationsApi.endpoints.markNotificationRead.matchFulfilled,
        (state, { payload }) => {
          state.items = state.items.filter((n) => n._id !== payload._id);
        }
      )
      // After marking all read — wipe local list
      .addMatcher(
        notificationsApi.endpoints.markAllNotificationsRead.matchFulfilled,
        (state) => {
          state.items = [];
        }
      );
  },
});

export const {
  setPendingNotifications,
  addNotification,
  clearAllNotifications,
} = notificationsSlice.actions;

export default notificationsSlice.reducer;

// ── Selectors ─────────────────────────────────────────────────────────────────
export const selectNotifications = (state: { notifications: NotificationsState }) =>
  state.notifications.items;
export const selectUnreadCount = (state: { notifications: NotificationsState }) =>
  state.notifications.items.length;
