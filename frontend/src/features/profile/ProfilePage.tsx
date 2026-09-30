import { useState } from "react";
import { useSearchParams } from "react-router-dom";

import { usePageTitle } from "@/shared/hooks/usePageTitle";
import { AppLink } from "@/shared/ui/AppLink";
import { PageError, PageLoader } from "@/shared/ui/PageState";

import { useProfile } from "./api";
import { AccountCard } from "./AccountCard";
import type { NoticeState } from "@/shared/ui/Notice";
import { ProfileForm } from "./ProfileForm";
import { ProfileSummaryCard } from "./ProfileSummaryCard";

/** The Yandex link callback comes back with ?info= or ?error=. */
function initialNotice(params: URLSearchParams): NoticeState | null {
  const error = params.get("error");
  if (error) return { kind: "error", text: error };
  const info = params.get("info");
  return info ? { kind: "success", text: info } : null;
}

export function ProfilePage() {
  usePageTitle("Профиль");
  const { data: profile, isPending, isError } = useProfile();
  const [params] = useSearchParams();
  const [notice, setNotice] = useState<NoticeState | null>(() => initialNotice(params));

  if (isPending) return <PageLoader />;
  if (isError) return <PageError />;

  return (
    <>
      <section className="hero">
        <p className="eyebrow">Профиль</p>
        <h1>Личные данные</h1>
      </section>
      <div className="dashboard-grid">
        <ProfileSummaryCard profile={profile} notice={notice} />
        <ProfileForm profile={profile} onNotice={setNotice} />
        <AccountCard profile={profile} onNotice={setNotice} />
      </div>
      <p className="back-link">
        {profile.is_admin && (
          <>
            <a href="/admin">Админ-панель</a> ·{" "}
          </>
        )}
        <AppLink to="/cabinet">← Вернуться в кабинет</AppLink>
      </p>
    </>
  );
}
