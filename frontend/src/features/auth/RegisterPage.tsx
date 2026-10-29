import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";

import { useSession } from "@/features/session/useSession";
import { errorMessage } from "@/shared/api/errors";
import { usePageTitle } from "@/shared/hooks/usePageTitle";
import { AppLink } from "@/shared/ui/AppLink";
import { Field } from "@/shared/ui/Field";
import { SelectField } from "@/shared/ui/SelectField";

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
  const [displayName, setDisplayName] = useState("");
  const [employmentFormat, setEmploymentFormat] = useState<
    "self_employed" | "individual_entrepreneur" | "individual"
  >("self_employed");
  const [payoutDetails, setPayoutDetails] = useState("");
  const [inn, setInn] = useState("");

  function submit(event: FormEvent) {
    event.preventDefault();
    register.mutate(
      {
        email,
        password,
        password_repeat: passwordRepeat,
        display_name: displayName,
        employment_format: employmentFormat,
        payout_details: payoutDetails,
        inn,
      },
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
          label="ФИО"
          name="display_name"
          maxLength={200}
          required
          autoComplete="name"
          value={displayName}
          onChange={(event) => setDisplayName(event.target.value)}
        />
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
        <SelectField
          label="Формат сотрудничества"
          name="employment_format"
          required
          emptyLabel={null}
          options={[
            { value: "self_employed", label: "Самозанятый" },
            { value: "individual_entrepreneur", label: "ИП" },
            { value: "individual", label: "Физическое лицо" },
          ]}
          value={employmentFormat}
          onChange={(event) =>
            setEmploymentFormat(event.target.value as typeof employmentFormat)
          }
        />
        <Field
          label="Реквизиты для выплат"
          name="payout_details"
          maxLength={200}
          required
          placeholder="Номер карты или расчётный счёт"
          value={payoutDetails}
          onChange={(event) => setPayoutDetails(event.target.value)}
        />
        <Field
          label="ИНН"
          name="inn"
          maxLength={12}
          required={employmentFormat !== "individual"}
          placeholder="10 или 12 цифр"
          value={inn}
          onChange={(event) => setInn(event.target.value)}
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
