import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";

import { useSession } from "@/features/session/useSession";
import { errorMessage } from "@/shared/api/errors";
import { usePageTitle } from "@/shared/hooks/usePageTitle";
import { AppLink } from "@/shared/ui/AppLink";
import { Field } from "@/shared/ui/Field";

import { useRegister } from "./api";
import { AuthCard } from "./AuthCard";
import { SocialLogin } from "./SocialLogin";

export function RegisterPage() {
  usePageTitle("Регистрация");
  const navigate = useNavigate();
  const { data: session } = useSession();
  const register = useRegister();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [passwordRepeat, setPasswordRepeat] = useState("");

  function submit(event: FormEvent) {
    event.preventDefault();
    register.mutate(
      { email, password, password_repeat: passwordRepeat },
      { onSuccess: ({ info }) => navigate("/register/confirm", { state: { info } }) },
    );
  }

  return (
    <AuthCard
      eyebrow="Агентская программа"
      title="Регистрация"
      error={register.isError ? errorMessage(register.error) : ""}
    >
      <SocialLogin yandexLabel="Регистрация через Яндекс" />
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
          minLength={6}
          required
          autoComplete="new-password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
        />
        <Field
          label="Повторите пароль"
          type="password"
          name="password_repeat"
          minLength={6}
          required
          autoComplete="new-password"
          value={passwordRepeat}
          onChange={(event) => setPasswordRepeat(event.target.value)}
        />
        <button className="button" type="submit" disabled={!session || register.isPending}>
          Получить код
        </button>
      </form>
      <p>
        <AppLink to="/login">Уже есть аккаунт</AppLink>
      </p>
    </AuthCard>
  );
}
