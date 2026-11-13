import { useState, type FormEvent } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { errorMessage } from "@/shared/api/errors";
import { usePageTitle } from "@/shared/hooks/usePageTitle";
import { AppLink } from "@/shared/ui/AppLink";
import { PageBack } from "@/shared/ui/PageBack";
import { Field } from "@/shared/ui/Field";
import { SelectField } from "@/shared/ui/SelectField";
import { PageError, PageLoader } from "@/shared/ui/PageState";

import { usePartner, useSavePartner } from "./api";
import type { EmploymentFormat, PartnerDetails } from "./types";

export function PartnerEditorPage() {
  const { agentId } = useParams();
  const id = agentId === undefined ? null : Number(agentId);
  usePageTitle(id === null ? "Создать партнёра" : "Редактировать партнёра");
  const detail = usePartner(Number.isSafeInteger(id) && Number(id) > 0 ? id : null);
  if (id !== null) {
    if (!Number.isSafeInteger(id) || id < 1) return <PageError />;
    if (detail.isPending) return <PageLoader />;
    if (detail.isError) return <PageError />;
    if (detail.data?.is_admin) {
      return (
        <>
          <PageBack to="/admin/partners">← К партнёрам</PageBack>
          <section className="card">
            <h1>Аккаунт администратора</h1>
            <p>Изменение администраторов недоступно в форме партнёра.</p>
          </section>
        </>
      );
    }
  }
  return <PartnerForm key={id ?? "new"} id={id} partner={detail.data} />;
}

function PartnerForm({ id, partner }: { id: number | null; partner?: PartnerDetails }) {
  const save = useSavePartner(id);
  const navigate = useNavigate();
  const [name, setName] = useState(partner?.display_name ?? "");
  const [email, setEmail] = useState(partner?.email ?? "");
  const [phone, setPhone] = useState(partner?.phone ?? "");
  const [format, setFormat] = useState<EmploymentFormat>(
    partner?.employment_format ?? "individual",
  );
  const [details, setDetails] = useState(partner?.payout_details ?? "");
  const [inn, setInn] = useState(partner?.inn ?? "");
  const [note, setNote] = useState(partner?.admin_note ?? "");

  function submit(event: FormEvent) {
    event.preventDefault();
    save.mutate(
      {
        display_name: name,
        phone,
        employment_format: format,
        payout_details: details,
        inn,
        admin_note: note,
        ...(id === null ? { email } : {}),
      },
      {
        onSuccess: (result) =>
          navigate(`/admin/partners?q=${encodeURIComponent(result.email ?? result.display_name)}`, {
            state: {
              info:
                id === null
                  ? "Партнёр создан. Сгенерированный пароль сохранён в админской заметке. Передайте его партнёру для входа по почте или номеру из аккаунта."
                  : "Данные партнёра сохранены.",
            },
          }),
      },
    );
  }

  return (
    <>
      <PageBack to="/admin/partners">← Партнёры</PageBack>
      <section className="card admin-partner-form">
        <p className="eyebrow">Управление партнёрами</p>
        <h1>{id === null ? "Новый партнёр" : "Редактировать партнёра"}</h1>
        <p className="admin-form-help">
          {id === null
            ? "Заполните контакты и реквизиты. Почта необязательна. Пароль из 8 английских букв и цифр создастся автоматически и сохранится в админской заметке. Для входа укажите хотя бы почту или телефон."
            : "Обновите личные данные и реквизиты. Пригласивший партнёр, история начислений и доступ к аккаунту сохранятся."}
        </p>
        {save.isError && (
          <p className="alert" role="alert">
            {errorMessage(save.error)}
          </p>
        )}
        <form onSubmit={submit}>
          <div className="admin-form-grid">
            <Field
              label="ФИО"
              name="display_name"
              autoComplete="name"
              maxLength={200}
              required
              value={name}
              onChange={(event) => setName(event.target.value)}
            />
            <Field
              label="Почта"
              name="email"
              type="email"
              autoComplete="email"
              maxLength={254}
              readOnly={id !== null}
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />
            <Field
              label="Телефон"
              name="phone"
              type="tel"
              autoComplete="tel"
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
              value={format}
              onChange={(event) => setFormat(event.target.value as EmploymentFormat)}
              options={[
                { value: "individual", label: "Физическое лицо" },
                { value: "self_employed", label: "Самозанятый" },
                { value: "individual_entrepreneur", label: "ИП" },
              ]}
            />
            <Field
              label="ИНН"
              name="inn"
              maxLength={12}
              inputMode="numeric"
              required={format !== "individual"}
              placeholder="10 или 12 цифр"
              value={inn}
              onChange={(event) => setInn(event.target.value)}
            />
            <Field
              label="Реквизиты для выплат"
              name="payout_details"
              maxLength={200}
              required
              placeholder="Номер карты или расчётный счёт"
              value={details}
              onChange={(event) => setDetails(event.target.value)}
            />
            <label className="admin-form-wide">
              Заметка для команды
              <textarea
                name="admin_note"
                rows={3}
                maxLength={id === null ? 1983 : 2000}
                value={note}
                onChange={(event) => setNote(event.target.value)}
              />
            </label>
          </div>
          {id !== null && (
            <p className="admin-form-help">
              Почта — идентификатор входа. Партнёр может изменить её в своём профиле с
              подтверждением.
            </p>
          )}
          <div className="footer-actions">
            <button className="button" type="submit" disabled={save.isPending}>
              {save.isPending
                ? "Сохраняем…"
                : id === null
                  ? "Создать партнёра"
                  : "Сохранить изменения"}
            </button>
            <AppLink className="button secondary" to="/admin/partners">
              Отмена
            </AppLink>
          </div>
        </form>
      </section>
    </>
  );
}
