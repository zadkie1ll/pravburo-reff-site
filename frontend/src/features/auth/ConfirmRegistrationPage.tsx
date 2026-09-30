import { useState, type FormEvent } from "react";

import { useSession } from "@/features/session/useSession";
import { errorMessage } from "@/shared/api/errors";
import { usePageTitle } from "@/shared/hooks/usePageTitle";
import { Field } from "@/shared/ui/Field";

import { useConfirmRegistration } from "./api";
import { AuthCard } from "./AuthCard";
import { useInfoFromNavigation } from "./useInfoFromNavigation";

export function ConfirmRegistrationPage() {
  usePageTitle("Подтверждение");
  const info = useInfoFromNavigation();
  const { data: session } = useSession();
  const confirm = useConfirmRegistration();
  const [code, setCode] = useState("");

  function submit(event: FormEvent) {
    event.preventDefault();
    confirm.mutate(code);
  }

  return (
    <AuthCard
      title="Подтвердите почту"
      info={info}
      error={confirm.isError ? errorMessage(confirm.error) : ""}
    >
      <p>Введите шестизначный код из письма.</p>
      <form onSubmit={submit}>
        <Field
          label="Код"
          name="code"
          inputMode="numeric"
          pattern="[0-9]{6}"
          maxLength={6}
          required
          autoComplete="one-time-code"
          value={code}
          onChange={(event) => setCode(event.target.value)}
        />
        <button className="button" type="submit" disabled={!session || confirm.isPending}>
          Подтвердить
        </button>
      </form>
    </AuthCard>
  );
}
