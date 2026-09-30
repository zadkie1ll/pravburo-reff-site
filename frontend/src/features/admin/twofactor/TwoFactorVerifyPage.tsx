import { AuthCard } from "@/features/auth/AuthCard";
import { errorMessage } from "@/shared/api/errors";
import { usePageTitle } from "@/shared/hooks/usePageTitle";

import { useSubmitCode } from "./api";
import { CodeForm } from "./CodeForm";
import { TwoFactorGate } from "./TwoFactorGate";

function VerifyCard() {
  const submit = useSubmitCode("verify");
  return (
    <AuthCard
      eyebrow="Администратор"
      title="Введите код из приложения"
      error={submit.isError ? errorMessage(submit.error) : ""}
    >
      <p>Откройте приложение-аутентификатор и введите текущий шестизначный код.</p>
      <CodeForm
        submitLabel="Войти"
        autoFocus
        pending={submit.isPending}
        onSubmit={(code, clear) => submit.mutate(code, { onError: clear })}
      />
    </AuthCard>
  );
}

export function TwoFactorVerifyPage() {
  usePageTitle("Код подтверждения");
  return <TwoFactorGate step="verify">{() => <VerifyCard />}</TwoFactorGate>;
}
