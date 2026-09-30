import { useEffect } from "react";

/** Full page navigation to a page that is still rendered by the backend. */
export function ServerRedirect({ to }: { to: string }) {
  useEffect(() => {
    window.location.replace(to);
  }, [to]);
  return null;
}
