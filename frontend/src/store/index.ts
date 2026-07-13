import { configureStore } from "@reduxjs/toolkit";

// Base RTK Query API (must be imported first so reducerPath is registered)
import { baseApi } from "./api/baseApi";

// All injected endpoint modules must be imported here so their
// endpoints are registered before any component tries to use them.
import "./api/authApi";
import "./api/roomsApi";
import "./api/messagesApi";
import "./api/notificationsApi";
import "./api/uploadApi";

// Slices
import authReducer from "./slices/authSlice";
import chatReducer from "./slices/chatSlice";
import notificationsReducer from "./slices/notificationsSlice";

export const store = configureStore({
  reducer: {
    // RTK Query cache reducer — key must match baseApi.reducerPath ("api")
    [baseApi.reducerPath]: baseApi.reducer,

    // Feature slices
    auth: authReducer,
    chat: chatReducer,
    notifications: notificationsReducer,
  },
  middleware: (getDefaultMiddleware) =>
    // RTK Query middleware handles cache lifetime, polling, invalidation
    getDefaultMiddleware().concat(baseApi.middleware),

  devTools: import.meta.env.DEV,
});

// Inferred types — import these in components via the hooks below
export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;
