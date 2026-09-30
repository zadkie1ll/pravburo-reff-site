import { useState, type FormEvent } from "react";

import { homeHref } from "@/app/layout/navigation";
import { useSession } from "@/features/session/useSession";
import { errorMessage } from "@/shared/api/errors";
import { usePageTitle } from "@/shared/hooks/usePageTitle";
import { ExternalLink } from "@/shared/ui/ExternalLink";
import { PageError, PageLoader } from "@/shared/ui/PageState";
import { ServerRedirect } from "@/shared/ui/ServerRedirect";

import { useChooseFormat, useOnboardingOptions } from "./api";
import type { EmploymentFormat } from "./types";

export function OnboardingPage() {
  usePageTitle("Выберите формат сотрудничества");
  const { data: session } = useSession();
  const { data, isPending, isError } = useOnboardingOptions();
  const choose = useChooseFormat();
  const [selected, setSelected] = useState<EmploymentFormat | null>(null);

  // Already chose a format (or an admin): nothing to do here.
  if (session && !session.onboarding_required) {
    return <ServerRedirect to={homeHref(session.role, session.authenticated)} />;
  }
  if (isPending) return <PageLoader />;
  if (isError) return <PageError />;

  function submit(event: FormEvent) {
    event.preventDefault();
    if (selected) choose.mutate(selected);
  }

  return (
    <>
      <section className="hero">
        <p className="eyebrow">Первый вход</p>
        <h1>Выберите формат сотрудничества</h1>
        <p>Выберите вариант, чтобы продолжить работу в личном кабинете.</p>
      </section>

      <section className="card">
        {choose.isError && (
          <div className="alert" role="alert">
            {errorMessage(choose.error)}
          </div>
        )}
        <form onSubmit={submit}>
          <h2>Есть три варианта</h2>
          <div className="option-list">
            {data.options.map((option) => (
              <label className="option-card" key={option.value}>
                <input
                  type="radio"
                  name="employment_format"
                  value={option.value}
                  required
                  checked={selected === option.value}
                  onChange={() => setSelected(option.value)}
                />
                <span className="option-body">
                  <strong>{option.title}</strong>
                  <span>{option.text}</span>
                </span>
              </label>
            ))}
          </div>
          <button className="button" type="submit" disabled={!selected || choose.isPending}>
            Продолжить
          </button>
        </form>
      </section>

      <section className="card">
        <h2>Ни один вариант не подходит?</h2>
        <p>
          Если ни один из вариантов вам не подходит, нужна помощь в выборе или вы сейчас проходите
          процедуру банкротства — напишите менеджеру, разберём вашу ситуацию индивидуально.
        </p>
        <ExternalLink className="button secondary" href={data.telegram_manager_url}>
          Написать менеджеру
        </ExternalLink>
      </section>
    </>
  );
}
