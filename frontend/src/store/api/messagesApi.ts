import { baseApi } from "./baseApi";
import type { Message } from "../types";

export const messagesApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    // ── PUT /messages/{messageId} ─────────────────────────────────────────────
    editMessage: build.mutation<Message, { messageId: string; content: string }>({
      query: ({ messageId, content }) => ({
        url: `/messages/${messageId}`,
        method: "PUT",
        body: { content },
      }),
      // Don't invalidate — the WS message.updated event updates local state
    }),

    // ── DELETE /messages/{messageId} ──────────────────────────────────────────
    deleteMessage: build.mutation<Message, string>({
      query: (messageId) => ({
        url: `/messages/${messageId}`,
        method: "DELETE",
      }),
      // Don't invalidate — the WS message.deleted event updates local state
    }),

    // ── PUT /messages/{messageId}/react ───────────────────────────────────────
    reactToMessage: build.mutation<
      Message,
      { messageId: string; emoji: string }
    >({
      query: ({ messageId, emoji }) => ({
        url: `/messages/${messageId}/react`,
        method: "PUT",
        body: { emoji },
      }),
      // Don't invalidate — the WS message.reaction event patches local state
    }),
  }),
  overrideExisting: false,
});

export const {
  useEditMessageMutation,
  useDeleteMessageMutation,
  useReactToMessageMutation,
} = messagesApi;
