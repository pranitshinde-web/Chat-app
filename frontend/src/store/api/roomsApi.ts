import { baseApi } from "./baseApi";
import type { Room, RoomCreate, RoomUpdate, RoomPresenceMember, Message } from "../types";

export const roomsApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    // ── GET /rooms/ ─────────────────────────────────────────────────────────
    listPublicRooms: build.query<
      Room[],
      { skip?: number; limit?: number; search?: string } | void
    >({
      query: (params = {}) => ({
        url: "/rooms/",
        params: {
          skip: params?.skip ?? 0,
          limit: params?.limit ?? 20,
          ...(params?.search ? { search: params.search } : {}),
        },
      }),
      providesTags: (result) =>
        result
          ? [
              ...result.map(({ _id }) => ({ type: "Room" as const, id: _id })),
              { type: "Room", id: "LIST" },
            ]
          : [{ type: "Room", id: "LIST" }],
    }),

    // ── GET /rooms/my ───────────────────────────────────────────────────────
    getMyRooms: build.query<Room[], void>({
      query: () => "/rooms/my",
      providesTags: (result) =>
        result
          ? [
              ...result.map(({ _id }) => ({ type: "Room" as const, id: _id })),
              { type: "Room", id: "MY" },
            ]
          : [{ type: "Room", id: "MY" }],
    }),

    // ── GET /rooms/{roomId} ─────────────────────────────────────────────────
    getRoom: build.query<Room, string>({
      query: (roomId) => `/rooms/${roomId}`,
      providesTags: (_, __, id) => [{ type: "Room", id }],
    }),

    // ── POST /rooms/ ────────────────────────────────────────────────────────
    createRoom: build.mutation<Room, RoomCreate>({
      query: (body) => ({
        url: "/rooms/",
        method: "POST",
        body,
      }),
      invalidatesTags: [{ type: "Room", id: "LIST" }, { type: "Room", id: "MY" }],
    }),

    // ── PUT /rooms/{roomId} ─────────────────────────────────────────────────
    updateRoom: build.mutation<Room, { roomId: string } & RoomUpdate>({
      query: ({ roomId, ...body }) => ({
        url: `/rooms/${roomId}`,
        method: "PUT",
        body,
      }),
      invalidatesTags: (_, __, { roomId }) => [{ type: "Room", id: roomId }],
    }),

    // ── POST /rooms/{roomId}/join ────────────────────────────────────────────
    joinRoom: build.mutation<Room, string>({
      query: (roomId) => ({
        url: `/rooms/${roomId}/join`,
        method: "POST",
      }),
      invalidatesTags: (_, __, roomId) => [
        { type: "Room", id: roomId },
        { type: "Room", id: "LIST" },
        { type: "Room", id: "MY" },
      ],
    }),

    // ── POST /rooms/{roomId}/leave ───────────────────────────────────────────
    leaveRoom: build.mutation<Room, string>({
      query: (roomId) => ({
        url: `/rooms/${roomId}/leave`,
        method: "POST",
      }),
      invalidatesTags: (_, __, roomId) => [
        { type: "Room", id: roomId },
        { type: "Room", id: "MY" },
      ],
    }),

    // ── GET /rooms/{roomId}/messages ─────────────────────────────────────────
    getRoomMessages: build.query<
      Message[],
      { roomId: string; limit?: number; before?: string }
    >({
      query: ({ roomId, limit = 50, before }) => ({
        url: `/rooms/${roomId}/messages`,
        params: { limit, ...(before ? { before } : {}) },
      }),
      // Tag per room so WS updates can target invalidation precisely
      providesTags: (_, __, { roomId }) => [{ type: "Message", id: roomId }],
    }),

    // ── POST /rooms/{roomId}/messages/read ────────────────────────────────────
    markRoomMessagesRead: build.mutation<void, string>({
      query: (roomId) => ({
        url: `/rooms/${roomId}/messages/read`,
        method: "POST",
      }),
      invalidatesTags: (_, __, roomId) => [{ type: "Message", id: roomId }],
    }),

    // ── GET /rooms/{roomId}/presence ─────────────────────────────────────────
    getRoomPresence: build.query<RoomPresenceMember[], string>({
      query: (roomId) => `/rooms/${roomId}/presence`,
      // Presence is live via WebSocket — short cache window is fine
      keepUnusedDataFor: 30,
    }),
  }),
  overrideExisting: false,
});

export const {
  useListPublicRoomsQuery,
  useGetMyRoomsQuery,
  useGetRoomQuery,
  useCreateRoomMutation,
  useUpdateRoomMutation,
  useJoinRoomMutation,
  useLeaveRoomMutation,
  useGetRoomMessagesQuery,
  useMarkRoomMessagesReadMutation,
  useGetRoomPresenceQuery,
} = roomsApi;
