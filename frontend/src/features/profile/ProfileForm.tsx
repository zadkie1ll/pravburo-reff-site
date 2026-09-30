import { useState, type FormEvent } from "react";

import { errorMessage } from "@/shared/api/errors";
import { Field } from "@/shared/ui/Field";
import { SelectField } from "@/shared/ui/SelectField";

import { useUpdateProfile } from "./api";
import type { NoticeState } from "@/shared/ui/Notice";
import type { Profile } from "./types";

interface ProfileFormProps {
  profile: Profile;
  onNotice: (notice: NoticeState) => void;
}

export function ProfileForm({ profile, onNotice }: ProfileFormProps) {
  const update = useUpdateProfile();
  const [displayName, setDisplayName] = useState(profile.display_name);
  const [phone, setPhone] = useState(profile.phone ?? "");
  // An admin has no format yet: like the old page, the first option is preselected.
  const [format, setFormat] = useState(
    profile.employment_format ?? profile.employment_formats[0]?.value ?? "individual",
  );
  const [payoutDetails, setPayoutDetails] = useState(profile.payout_details ?? "");
  const [inn, setInn] = useState(profile.inn ?? "");

  function submit(event: FormEvent) {
    event.preventDefault();
    update.mutate(
      {
        display_name: displayName,
        phone,
        employment_format: format,
        payout_details: payoutDetails,
        inn,
      },
      {
        onSuccess: () => onNotice({ kind: "success", text: "Профиль обновлён" }),
        onError: (error) => onNotice({ kind: "error", text: errorMessage(error) }),
      },
    );
  }

  return (
    <section className="card">
      <h2>Изменить данные</h2>
      <form className="lead-form" onSubmit={submit}>
        <Field
          label="ФИО"
          name="display_name"
          maxLength={200}
          value={displayName}
          onChange={(event) => setDisplayName(event.target.value)}
        />
        <Field
          label="Телефон"
          type="tel"
          name="phone"
          maxLength={20}
          placeholder="+7 999 000-00-00"
          value={phone}
          onChange={(event) => setPhone(event.target.value)}
        />
        <SelectField
          label="Формат сотрудничества"
          name="employment_format"
          required
          emptyLabel={null}
          options={profile.employment_formats}
          value={format}
          onChange={(event) => setFormat(event.target.value as typeof format)}
        />
        <Field
          label="Реквизиты для выплат"
          name="payout_details"
          maxLength={200}
          placeholder="Номер карты или расчётный счёт"
          value={payoutDetails}
          onChange={(event) => setPayoutDetails(event.target.value)}
        />
        <Field
          label="ИНН"
          name="inn"
          maxLength={12}
          placeholder="10 или 12 цифр, для самозанятых и ИП"
          value={inn}
          onChange={(event) => setInn(event.target.value)}
        />
        <button className="button" type="submit" disabled={update.isPending}>
          Сохранить
        </button>
      </form>
    </section>
  );
}
