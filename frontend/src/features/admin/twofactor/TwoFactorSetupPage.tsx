import { AuthCard } from "@/features/auth/AuthCard";
import { errorMessage } from "@/shared/api/errors";
import { usePageTitle } from "@/shared/hooks/usePageTitle";

import { useSubmitCode } from "./api";
import { CodeForm } from "./CodeForm";
import { TwoFactorGate } from "./TwoFactorGate";

function SetupCard({ qrUrl }: { qrUrl: string | null }) {
  const submit = useSubmitCode("setup");
  return (
    <AuthCard
      eyebrow="Администратор"
      title="Настройте двухфакторную аутентификацию"
      error={submit.isError ? errorMessage(submit.error) : ""}
    >
      <p>
        Отсканируйте QR-код в приложении Google Authenticator, Яндекс.Ключ или похожем, затем
        введите код из приложения, чтобы подтвердить настройку.
      </p>
      {qrUrl && <img className="qr" src={qrUrl} alt="QR-код для настройки 2FA" />}
      <CodeForm
        submitLabel="Подтвердить и включить"
        pending={submit.isPending}
        onSubmit={(code, clear) => submit.mutate(code, { onError: clear })}
      />
    </AuthCard>
  );
}

export function TwoFactorSetupPage() {
  usePageTitle("Настройка 2FA");
  return (
    <TwoFactorGate step="setup">{(state) => <SetupCard qrUrl={state.qr_url} />}</TwoFactorGate>
  );
}
