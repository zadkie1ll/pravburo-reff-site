import { useState, type FormEvent } from "react";

import { useSession } from "@/features/session/useSession";
import { errorMessage } from "@/shared/api/errors";
import { usePageTitle } from "@/shared/hooks/usePageTitle";
import { Field } from "@/shared/ui/Field";

import { useConfirmPasswordReset } from "./api";
import { AuthCard } from "./AuthCard";
import { useInfoFromNavigation } from "./useInfoFromNavigation";

export function PasswordResetConfirmPage() {
  usePageTitle("Новый пароль");
  const info = useInfoFromNavigation();
  const { data: session } = useSession();
  const confirm = useConfirmPasswordReset();
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [passwordRepeat, setPasswordRepeat] = useState("");

  function submit(event: FormEvent) {
    event.preventDefault();
    confirm.mutate({ code, password, password_repeat: passwordRepeat });
  }

  return (
    <AuthCard
      title="Новый пароль"
      info={info}
      error={confirm.isError ? errorMessage(confirm.error) : ""}
    >
      <form onSubmit={submit}>
        <Field
          label="Код"
          name="code"
          maxLength={6}
          required
          autoComplete="one-time-code"
          value={code}
          onChange={(event) => setCode(event.target.value)}
        />
        <Field
          label="Новый пароль"
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
        <button className="button" type="submit" disabled={!session || confirm.isPending}>
          Сохранить
        </button>
      </form>
    </AuthCard>
  );
}
