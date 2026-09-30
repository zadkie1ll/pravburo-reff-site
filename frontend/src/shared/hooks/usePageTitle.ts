import { useEffect } from "react";

const SITE_NAME = "Правбюро";

export function usePageTitle(title?: string): void {
  useEffect(() => {
    document.title = title ? `${title} · ${SITE_NAME}` : SITE_NAME;
  }, [title]);
}
