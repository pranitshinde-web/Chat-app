import { createSlice } from "@reduxjs/toolkit";
import type { PayloadAction } from "@reduxjs/toolkit";
import type { Message } from "../types";

// ── Types ─────────────────────────────────────────────────────────────────────

export type WSConnectionStatus = "idle" | "connecting" | "connected" | "error" | "disconnected";

export interface TypingUser {
  user_id: string;
  username: string;
}

interface ChatState {
  /** Room the user is currently viewing */
  activeRoomId: string | null;
  /** WebSocket connection status for the active room */
  wsStatus: WSConnectionStatus;
  /**
   * Ordered messages for the active room.
   * Seeded from the REST history fetch (oldest → newest),
   * then appended to in real time via WebSocket events.
   */
  messages: Message[];
  /**
   * Whether the next scroll should load older messages
   * (cursor-based pagination — set after a successful history page).
   */
  hasMore: boolean;
  /** Users currently typing in the active room */
  typingUsers: TypingUser[];
}

const initialState: ChatState = {
  activeRoomId: null,
  wsStatus: "idle",
  messages: [],
  hasMore: false,
  typingUsers: [],
};

// ── Slice ─────────────────────────────────────────────────────────────────────

const chatSlice = createSlice({
  name: "chat",
  initialState,
  reducers: {
    // ── Room navigation ─────────────────────────────────────────────────────

    /** Switch to a new room — resets all transient room state. */
    setActiveRoom(state, action: PayloadAction<string | null>) {
      state.activeRoomId = action.payload;
      state.messages = [];
      state.typingUsers = [];
      state.hasMore = false;
      state.wsStatus = "idle";
    },

    // ── WebSocket connection ────────────────────────────────────────────────

    setWSStatus(state, action: PayloadAction<WSConnectionStatus>) {
      state.wsStatus = action.payload;
    },

    // ── Message list management ─────────────────────────────────────────────

    /**
     * Seed messages from the REST history response.
     * The API returns newest-first; we reverse to oldest-first for display.
     * Call with the full first page on room open, or prepend=true for older pages.
     */
    seedMessages(
      state,
      action: PayloadAction<{ messages: Message[]; prepend?: boolean }>
    ) {
      const sorted = [...action.payload.messages].reverse(); // oldest → newest
      if (action.payload.prepend) {
        // Older page fetched by scroll-up — prepend without duplicates
        const existingIds = new Set(state.messages.map((m) => m._id));
        state.messages = [...sorted.filter((m) => !existingIds.has(m._id)), ...state.messages];
      } else {
        state.messages = sorted;
      }
      // If the page was full (50 items) there's likely more history
      state.hasMore = action.payload.messages.length >= 50;
    },

    /**
     * Append a single new message from a WebSocket message.new event.
     * Deduplicates so a sender who gets both message.sent and message.new
     * doesn't see a double.
     */
    addMessage(state, action: PayloadAction<Message>) {
      if (!state.messages.some((m) => m._id === action.payload._id)) {
        state.messages.push(action.payload);
      }
    },

    /**
     * Replace a message in-place — used for message.updated events.
     */
    updateMessage(state, action: PayloadAction<Message>) {
      const idx = state.messages.findIndex((m) => m._id === action.payload._id);
      if (idx !== -1) {
        state.messages[idx] = action.payload;
      }
    },

    /**
     * Patch only the reactions map on a message — used for message.reaction events.
     * More efficient than replacing the whole message.
     */
    patchReactions(
      state,
      action: PayloadAction<{
        message_id: string;
        reactions: Record<string, string[]>;
      }>
    ) {
      const msg = state.messages.find((m) => m._id === action.payload.message_id);
      if (msg) {
        msg.reactions = action.payload.reactions;
      }
    },

    /**
     * Patch the read_by list on a message — used for message.read_receipt events.
     */
    patchReadBy(
      state,
      action: PayloadAction<{ message_id: string; read_by: string[] }>
    ) {
      const msg = state.messages.find((m) => m._id === action.payload.message_id);
      if (msg) {
        msg.read_by = action.payload.read_by;
      }
    },

    // ── Typing indicators ───────────────────────────────────────────────────

    addTypingUser(state, action: PayloadAction<TypingUser>) {
      const exists = state.typingUsers.some(
        (u) => u.user_id === action.payload.user_id
      );
      if (!exists) {
        state.typingUsers.push(action.payload);
      }
    },

    removeTypingUser(state, action: PayloadAction<string>) {
      state.typingUsers = state.typingUsers.filter(
        (u) => u.user_id !== action.payload
      );
    },

    clearTypingUsers(state) {
      state.typingUsers = [];
    },
  },
});

export const {
  setActiveRoom,
  setWSStatus,
  seedMessages,
  addMessage,
  updateMessage,
  patchReactions,
  patchReadBy,
  addTypingUser,
  removeTypingUser,
  clearTypingUsers,
} = chatSlice.actions;

export default chatSlice.reducer;

// ── Selectors ─────────────────────────────────────────────────────────────────
export const selectActiveRoomId = (state: { chat: ChatState }) => state.chat.activeRoomId;
export const selectMessages = (state: { chat: ChatState }) => state.chat.messages;
export const selectWSStatus = (state: { chat: ChatState }) => state.chat.wsStatus;
export const selectTypingUsers = (state: { chat: ChatState }) => state.chat.typingUsers;
export const selectHasMore = (state: { chat: ChatState }) => state.chat.hasMore;
