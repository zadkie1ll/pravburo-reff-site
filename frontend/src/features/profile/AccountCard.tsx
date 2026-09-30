import { AppLink } from "@/shared/ui/AppLink";

import { EmailChange } from "./EmailChange";
import type { NoticeState } from "@/shared/ui/Notice";
import type { Profile } from "./types";

interface AccountCardProps {
  profile: Profile;
  onNotice: (notice: NoticeState) => void;
}

export function AccountCard({ profile, onNotice }: AccountCardProps) {
  return (
    <section className="card">
      <h2>Аккаунт</h2>
      <EmailChange profile={profile} onNotice={onNotice} />
      <p className="back-link">
        <AppLink to="/password/reset">Изменить пароль →</AppLink>
      </p>
      {profile.yandex_enabled && (
        <p className="back-link">
          {profile.yandex_linked ? (
            "Яндекс привязан"
          ) : (
            <a href="/auth/yandex/start">Привязать Яндекс →</a>
          )}
        </p>
      )}
    </section>
  );
}
