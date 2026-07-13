// ── Auth ──────────────────────────────────────────────────────────────────────

export interface User {
  _id: string;
  username: string;
  email: string;
  avatar_url: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface AuthResponse {
  user: User;
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface Token {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

// ── Rooms ─────────────────────────────────────────────────────────────────────

export type RoomType = "public" | "private" | "direct";

export interface Room {
  _id: string;
  name: string;
  description: string | null;
  type: RoomType;
  created_by: string;
  members: string[];
  created_at: string;
  updated_at: string;
}

export interface RoomCreate {
  name: string;
  description?: string;
  type: RoomType;
  members?: string[];
}

export interface RoomUpdate {
  name?: string;
  description?: string;
}

export interface RoomPresenceMember {
  user_id: string;
  username: string;
  avatar_url: string | null;
}

// ── Messages ──────────────────────────────────────────────────────────────────

export type MessageType = "text" | "image" | "file";

export interface Message {
  _id: string;
  room_id: string;
  sender_id: string;
  content: string | null;
  message_type: MessageType;
  file_url: string | null;
  /** emoji → array of user_ids who reacted */
  reactions: Record<string, string[]>;
  read_by: string[];
  is_deleted: boolean;
  created_at: string;
  updated_at: string;
}

// ── Notifications ─────────────────────────────────────────────────────────────

export type NotificationType = "new_message" | "mention" | "room_invite";

export interface Notification {
  _id: string;
  user_id: string;
  type: NotificationType;
  room_id: string | null;
  message_id: string | null;
  is_read: boolean;
  created_at: string;
  updated_at: string;
}

export interface NotificationListResponse {
  notifications: Notification[];
  unread_count: number;
}

// ── File upload ───────────────────────────────────────────────────────────────

export interface UploadResponse {
  file_url: string;
  filename: string;
  original_filename: string;
  content_type: string;
  size_bytes: number;
}

// ── WebSocket ─────────────────────────────────────────────────────────────────

export type WSEventType =
  | "message.send"
  | "message.new"
  | "message.sent"
  | "message.updated"
  | "message.deleted"
  | "message.reaction"
  | "typing.start"
  | "typing.stop"
  | "presence.join"
  | "presence.leave"
  | "message.read"
  | "message.read_receipt"
  | "room.read_all"
  | "notifications.pending"
  | "error";

export interface WSEvent<T = Record<string, unknown>> {
  event: WSEventType;
  payload: T;
  room_id: string;
  timestamp: string;
}

// ── WebSocket payload shapes (for typed dispatch in WS handler) ───────────────

export type WSMessageNewPayload = Message;

export interface WSReactionPayload {
  message_id: string;
  emoji: string;
  user_id: string;
  action: "added" | "removed";
  reactions: Record<string, string[]>;
}

export interface WSReadReceiptPayload {
  message_id: string;
  read_by: string[];
  reader_id: string;
}

export interface WSTypingPayload {
  user_id: string;
  username: string;
}

export interface WSPresencePayload {
  user_id: string;
  username: string;
}

export interface WSNotificationsPendingPayload {
  notifications: Notification[];
  unread_count: number;
}
