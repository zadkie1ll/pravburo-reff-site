import { useAuthConfig } from "./api";
import { TelegramLoginButton } from "./TelegramLoginButton";

interface SocialLoginProps {
  yandexLabel: string;
}

/** Yandex and Telegram sign-in; renders only what the backend has configured. */
export function SocialLogin({ yandexLabel }: SocialLoginProps) {
  const { data: config } = useAuthConfig();
  if (!config) return null;

  return (
    <>
      {config.yandex_enabled && (
        <p>
          <a className="button secondary" href="/auth/yandex/start">
            {yandexLabel}
          </a>
        </p>
      )}
      {config.telegram_bot_username && (
        <TelegramLoginButton
          botUsername={config.telegram_bot_username}
          authUrl={config.telegram_auth_url}
        />
      )}
    </>
  );
}
