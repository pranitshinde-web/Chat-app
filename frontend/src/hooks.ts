import { useDispatch, useSelector } from "react-redux";
import type { AppDispatch, RootState } from "./store/index";

/**
 * Use this instead of plain `useDispatch` to get full AppDispatch typing
 * (including thunk support if you add it later).
 */
export const useAppDispatch = () => useDispatch<AppDispatch>();

/**
 * Use this instead of plain `useSelector` for full RootState type inference.
 *
 * @example
 * const user = useAppSelector((s) => s.auth.user);
 * const messages = useAppSelector(selectMessages);
 */
export const useAppSelector = <T>(selector: (state: RootState) => T): T =>
  useSelector(selector);
