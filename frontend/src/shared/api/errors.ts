import { ApiError } from "./client";

/** Text for the user: the backend's message when there is one, otherwise a generic fallback. */
export function errorMessage(
  error: unknown,
  fallback = "Что-то пошло не так. Попробуйте ещё раз.",
): string {
  return error instanceof ApiError ? error.message : fallback;
}
