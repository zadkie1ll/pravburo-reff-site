import { Notice, type NoticeState } from "@/shared/ui/Notice";
import type { Profile } from "./types";

interface ProfileSummaryCardProps {
  profile: Profile;
  notice: NoticeState | null;
}

export function ProfileSummaryCard({ profile, notice }: ProfileSummaryCardProps) {
  const format = profile.employment_formats.find(
    (option) => option.value === profile.employment_format,
  );
  return (
    <section className="card">
      <h2>Основное</h2>
      <Notice notice={notice} />
      <dl className="details">
        <div>
          <dt>Телефон</dt>
          <dd>{profile.phone || "Не указан"}</dd>
        </div>
        <div>
          <dt>Email</dt>
          <dd>{profile.email || "Не указан"}</dd>
        </div>
        <div>
          <dt>Формат сотрудничества</dt>
          <dd>{format?.label ?? "Не указан"}</dd>
        </div>
        <div>
          <dt>Реквизиты для выплат</dt>
          <dd>{profile.payout_details || "Не указаны"}</dd>
        </div>
        <div>
          <dt>ИНН</dt>
          <dd>{profile.inn || "Не указан"}</dd>
        </div>
        <div>
          <dt>Дата регистрации</dt>
          <dd>{profile.registered_at_label}</dd>
        </div>
        <div>
          <dt>Статус аккаунта</dt>
          <dd>{profile.is_active ? "Активен" : "Приостановлен"}</dd>
        </div>
      </dl>
    </section>
  );
}
