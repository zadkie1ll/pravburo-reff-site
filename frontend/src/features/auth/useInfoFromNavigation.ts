import { useLocation } from "react-router-dom";

/** The notice the previous step passed along via router state (e.g. "code sent"). */
export function useInfoFromNavigation(): string {
  const { state } = useLocation() as { state: { info?: string } | null };
  return state?.info ?? "";
}
