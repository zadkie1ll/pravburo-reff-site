import { useEffect, useRef } from "react";

import { loadTurnstile } from "./turnstile";

interface TurnstileWidgetProps {
  siteKey: string;
  /** Called with the token when solved, and with "" when it expires or fails. */
  onToken: (token: string) => void;
  /** Change the value to get a fresh challenge (a token can be used only once). */
  resetSignal: number;
}

export function TurnstileWidget({ siteKey, onToken, resetSignal }: TurnstileWidgetProps) {
  const container = useRef<HTMLDivElement>(null);
  const widgetId = useRef<string | null>(null);
  const onTokenRef = useRef(onToken);

  useEffect(() => {
    onTokenRef.current = onToken;
  }, [onToken]);

  useEffect(() => {
    const host = container.current;
    if (!host) return;
    let cancelled = false;
    loadTurnstile()
      .then((turnstile) => {
        if (cancelled) return;
        widgetId.current = turnstile.render(host, {
          sitekey: siteKey,
          callback: (token) => onTokenRef.current(token),
          "expired-callback": () => onTokenRef.current(""),
          "error-callback": () => onTokenRef.current(""),
        });
      })
      .catch(() => onTokenRef.current(""));
    return () => {
      cancelled = true;
      if (widgetId.current !== null) window.turnstile?.remove(widgetId.current);
      widgetId.current = null;
    };
  }, [siteKey]);

  useEffect(() => {
    if (resetSignal > 0 && widgetId.current !== null) window.turnstile?.reset(widgetId.current);
  }, [resetSignal]);

  return <div ref={container} />;
}
