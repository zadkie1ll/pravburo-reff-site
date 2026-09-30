import { useState, type FormEvent } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { NotFoundPage } from "@/features/errors/NotFoundPage";
import { ApiError } from "@/shared/api/client";
import { errorMessage } from "@/shared/api/errors";
import { usePageTitle } from "@/shared/hooks/usePageTitle";
import { Field } from "@/shared/ui/Field";
import { PageError, PageLoader } from "@/shared/ui/PageState";

import { useReferralForm, useSubmitReferral } from "./api";
import { TurnstileWidget } from "./TurnstileWidget";

export function ReferralFormPage() {
  usePageTitle("Получить консультацию");
  const { referralCode = "" } = useParams();
  const navigate = useNavigate();
  const form = useReferralForm(referralCode);
  const submit = useSubmitReferral(referralCode);

  const [fullName, setFullName] = useState("");
  const [phone, setPhone] = useState("");
  const [callTime, setCallTime] = useState("");
  const [showDetails, setShowDetails] = useState(false);
  const [city, setCity] = useState("");
  const [debtAmount, setDebtAmount] = useState("");
  const [situation, setSituation] = useState("");
  const [website, setWebsite] = useState(""); // honeypot
  const [token, setToken] = useState("");
  const [captchaReset, setCaptchaReset] = useState(0);

  if (form.isPending) return <PageLoader />;
  if (form.isError) {
    const unknownLink = form.error instanceof ApiError && [404, 422].includes(form.error.status);
    return unknownLink ? <NotFoundPage /> : <PageError />;
  }

  const siteKey = form.data.turnstile_site_key;

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    submit.mutate(
      {
        full_name: fullName,
        phone,
        preferred_call_time_msk: callTime,
        city,
        debt_amount: debtAmount,
        situation,
        website,
        turnstile_token: token,
      },
      {
        onSuccess: () => navigate(`/r/${referralCode}/success`),
        onError: () => {
          // A Turnstile token works once: ask for a new one before the next attempt.
          setToken("");
          setCaptchaReset((count) => count + 1);
        },
      },
    );
  }

  return (
    <section className="form-layout">
      <div className="hero">
        <p className="eyebrow">Бесплатная консультация</p>
        <h1>Расскажите о вашей ситуации</h1>
        <p>Специалист Правбюро свяжется с вами в удобное время по Москве.</p>
      </div>
      <form className="card lead-form" onSubmit={onSubmit}>
        {submit.isError && (
          <div className="alert" role="alert">
            {errorMessage(submit.error)}
          </div>
        )}
        <Field
          label="ФИО"
          name="full_name"
          maxLength={200}
          required
          value={fullName}
          onChange={(event) => setFullName(event.target.value)}
        />
        <Field
          label="Телефон"
          type="tel"
          name="phone"
          maxLength={30}
          required
          value={phone}
          onChange={(event) => setPhone(event.target.value)}
        />
        <Field
          label="Удобное время звонка по МСК"
          name="preferred_call_time_msk"
          maxLength={100}
          placeholder="Например, с 15:00 до 18:00"
          value={callTime}
          onChange={(event) => setCallTime(event.target.value)}
        />
        {!showDetails && (
          <button type="button" className="text-button" onClick={() => setShowDetails(true)}>
            Описать свою ситуацию
          </button>
        )}
        {showDetails && (
          <div>
            <Field
              label="Город"
              name="city"
              maxLength={120}
              value={city}
              onChange={(event) => setCity(event.target.value)}
            />
            <Field
              label="Сумма долга"
              name="debt_amount"
              maxLength={80}
              value={debtAmount}
              onChange={(event) => setDebtAmount(event.target.value)}
            />
            <label>
              Описание ситуации
              <textarea
                name="situation"
                maxLength={3000}
                rows={6}
                value={situation}
                onChange={(event) => setSituation(event.target.value)}
              />
            </label>
          </div>
        )}
        {/* Honeypot: invisible to people, tempting to bots. */}
        <input
          className="honeypot"
          name="website"
          tabIndex={-1}
          autoComplete="off"
          aria-hidden="true"
          value={website}
          onChange={(event) => setWebsite(event.target.value)}
        />
        {siteKey && (
          <TurnstileWidget siteKey={siteKey} onToken={setToken} resetSignal={captchaReset} />
        )}
        <button
          className="button"
          type="submit"
          disabled={submit.isPending || (Boolean(siteKey) && !token)}
        >
          Отправить заявку
        </button>
      </form>
    </section>
  );
}
