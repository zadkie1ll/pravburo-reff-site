import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";

import { useSession } from "@/features/session/useSession";
import { errorMessage } from "@/shared/api/errors";
import { usePageTitle } from "@/shared/hooks/usePageTitle";
import { Field } from "@/shared/ui/Field";

import { useRequestPasswordReset } from "./api";
import { AuthCard } from "./AuthCard";

export function PasswordResetPage() {
  const { data: session } = useSession();
  // A logged-in partner changes the password; a guest recovers it.
  const isChange = session?.authenticated ?? false;
  usePageTitle(isChange ? "Смена пароля" : "Восстановление");

  const navigate = useNavigate();
  const request = useRequestPasswordReset();
  const [typedEmail, setTypedEmail] = useState<string | null>(null);
  const email = typedEmail ?? session?.email ?? "";

  function submit(event: FormEvent) {
    event.preventDefault();
    request.mutate(email, {
      onSuccess: ({ info }) => navigate("/password/reset/confirm", { state: { info } }),
    });
  }

  return (
    <AuthCard
      title={isChange ? "Изменить пароль" : "Восстановить пароль"}
      error={request.isError ? errorMessage(request.error) : ""}
    >
      <form onSubmit={submit}>
        <Field
          label="Почта"
          type="email"
          name="email"
          required
          value={email}
          onChange={(event) => setTypedEmail(event.target.value)}
        />
        <button className="button" type="submit" disabled={!session || request.isPending}>
          Получить код
        </button>
      </form>
    </AuthCard>
  );
}
