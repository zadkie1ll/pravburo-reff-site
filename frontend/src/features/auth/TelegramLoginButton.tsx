import { useEffect, useRef } from "react";

interface TelegramLoginButtonProps {
  botUsername: string;
  authUrl: string;
}

/** Telegram's official widget: it injects its own iframe into the script's parent. */
export function TelegramLoginButton({ botUsername, authUrl }: TelegramLoginButtonProps) {
  const container = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const host = container.current;
    if (!host) return;
    const script = document.createElement("script");
    script.async = true;
    script.src = "https://telegram.org/js/telegram-widget.js?22";
    script.dataset.telegramLogin = botUsername;
    script.dataset.size = "large";
    script.dataset.authUrl = authUrl;
    script.dataset.requestAccess = "write";
    host.appendChild(script);
    return () => host.replaceChildren();
  }, [botUsername, authUrl]);

  return <div className="telegram-login" ref={container} />;
}
