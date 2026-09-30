import { useState, type FormEvent } from "react";
import { useSearchParams } from "react-router-dom";

import { useSession } from "@/features/session/useSession";
import { errorMessage } from "@/shared/api/errors";
import { usePageTitle } from "@/shared/hooks/usePageTitle";
import { Field } from "@/shared/ui/Field";

import { useLogin } from "./api";
import { AuthCard } from "./AuthCard";
import { SocialLogin } from "./SocialLogin";

export function LoginPage() {
  usePageTitle("Вход");
  const [params] = useSearchParams();
  const { data: session } = useSession();
  const login = useLogin();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  // ?error= is set by the backend when a Telegram/Yandex callback fails.
  const error = login.isError
    ? errorMessage(login.error, "Не удалось выполнить вход. Попробуйте ещё раз.")
    : (params.get("error") ?? "");

  function submit(event: FormEvent) {
    event.preventDefault();
    login.mutate({ email, password });
  }

  return (
    <AuthCard eyebrow="Личный кабинет" title="Войти" error={error}>
      <form onSubmit={submit}>
        <Field
          label="Почта"
          type="email"
          name="email"
          required
          autoComplete="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
        />
        <Field
          label="Пароль"
          type="password"
          name="password"
          required
          autoComplete="current-password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
        />
        {/* The CSRF token comes with the session: no submit before it has loaded. */}
        <button className="button" type="submit" disabled={!session || login.isPending}>
          Войти
        </button>
      </form>
      <SocialLogin yandexLabel="Войти через Яндекс" />
      <p>
        <a href="/register">Создать аккаунт</a> · <a href="/password/reset">Забыли пароль?</a>
      </p>
    </AuthCard>
  );
}
