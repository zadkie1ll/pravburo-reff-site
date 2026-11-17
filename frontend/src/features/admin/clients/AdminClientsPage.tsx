import { useState, type FormEvent } from "react";
import { useSearchParams } from "react-router-dom";
import { useInfoFromNavigation } from "@/features/auth/useInfoFromNavigation";
import { errorMessage } from "@/shared/api/errors";
import { usePageTitle } from "@/shared/hooks/usePageTitle";
import { AppLink } from "@/shared/ui/AppLink";
import { Field } from "@/shared/ui/Field";
import { PageBack } from "@/shared/ui/PageBack";
import { Pagination } from "@/shared/ui/Pagination";
import { PageError, PageLoader } from "@/shared/ui/PageState";
import {
  clientsSearch,
  positiveId,
  useClients,
  useUpdateClient,
  useUpdateClientPayout,
  type ClientFilters,
  type ExistingClient,
} from "./api";
import { BitrixLink } from "./BitrixLink";
import { DeleteRecordButton } from "../deletions/DeleteRecordButton";
import { PartnerSelector } from "./PartnerSelector";

const money = (amount: string | null) =>
  amount === null
    ? "Не указано"
    : new Intl.NumberFormat("ru-RU", {
        style: "currency",
        currency: "RUB",
        maximumFractionDigits: 2,
      }).format(Number(amount));
const statuses: Record<string, string> = {
  pending: "Ожидает",
  approved: "Одобрено",
  scheduled: "Запланировано",
  overdue: "Просрочено",
  paid: "Выплачено",
  rejected: "Отклонено",
};

export function AdminClientsPage() {
  usePageTitle("Действующие клиенты");
  const info = useInfoFromNavigation();
  const [deletedNotice, setDeletedNotice] = useState("");
  const [params, setParams] = useSearchParams();
  const filters: ClientFilters = {
    q: params.get("q") ?? "",
    agentId: positiveId(params.get("agent_id")),
    page: positiveId(params.get("page")) ?? 1,
  };
  const { data, isPending, isError } = useClients(filters);
  const pagination = data && (
    <Pagination
      page={data.page}
      totalPages={data.total_pages}
      searchFor={(page) => clientsSearch({ ...filters, page })}
    />
  );

  return (
    <>
      <PageBack to="/admin?section=clients">← Действующие клиенты</PageBack>
      <section className="card">
        <div className="client-list-heading">
          <h1>Действующие клиенты</h1>
          <AppLink
            className="button"
            to={`/admin/clients/new${filters.agentId === null ? "" : `?agent_id=${filters.agentId}`}`}
          >
            Добавить клиента
          </AppLink>
        </div>
        <p className="admin-form-help">
          Клиенты с существующими сделками в Битрикс24 и текущие суммы к выплате.
        </p>
        <ClientFilterForm
          key={`${filters.q}|${filters.agentId}`}
          filters={filters}
          onApply={(next) => setParams(new URLSearchParams(clientsSearch(next)))}
        />
        {data && <p className="hint">Всего: {data.total_count}</p>}
      </section>
      {(info || deletedNotice) && (
        <p className="notice-success" role="status">
          {deletedNotice || info}
        </p>
      )}
      {isPending ? (
        <PageLoader />
      ) : isError ? (
        <PageError />
      ) : (
        <>
          {pagination}
          {data.rows.length === 0 ? (
            <section className="card mt-20">
              <p>Действующие клиенты не найдены</p>
            </section>
          ) : (
            <div className="partner-card-grid">
              {data.rows.map((row) => (
                <article
                  key={row.id}
                  className="partner-profile-card client-profile-card"
                  aria-label={`Клиент: ${row.full_name}`}
                >
                  <h2>{row.full_name}</h2>
                  <p>{row.phone || "Телефон не указан"}</p>
                  <dl className="client-details">
                    <div>
                      <dt>Партнёр</dt>
                      <dd>
                        {row.agent_name || `#${row.agent_id}`}
                        {row.agent_email && <small>{row.agent_email}</small>}
                      </dd>
                    </div>
                    <div>
                      <dt>Сделка Битрикс24</dt>
                      <dd>
                        #{row.bitrix_deal_id} <BitrixLink url={row.bitrix_deal_url} />
                      </dd>
                    </div>
                    <div>
                      <dt>Этап сделки</dt>
                      <dd>{row.stage_label || "Не указан"}</dd>
                    </div>
                    <div>
                      <dt>{row.workflow ? "Всего к выплате по клиенту" : "К выплате партнёру"}</dt>
                      <dd>{money(row.workflow?.outstanding ?? row.current_amount)}</dd>
                    </div>
                    <div>
                      <dt>Статус текущей выплаты</dt>
                      <dd>
                        {row.workflow
                          ? row.workflow.status_label
                          : row.current_status
                            ? (statuses[row.current_status] ?? row.current_status)
                            : "Не указан"}
                      </dd>
                    </div>
                    <div>
                      <dt>
                        {row.workflow
                          ? "Ближайший срок выплаты"
                          : row.current_status === "paid"
                            ? "Выплачено"
                            : "Выплатить партнёру до"}
                      </dt>
                      <dd>
                        {row.workflow
                          ? row.workflow.next_due_on?.split("-").reverse().join(".") ||
                            "Нет текущих выплат"
                          : row.payout_due_date_label || "Не указано"}
                      </dd>
                    </div>
                    <div>
                      <dt>Добавлен</dt>
                      <dd>{row.created_at_label}</dd>
                    </div>
                  </dl>
                  {row.admin_note && <p className="partner-note-preview">{row.admin_note}</p>}
                  {(row.workflow || row.current_amount === null) && (
                    <AppLink className="button" to={`/admin/clients/${row.id}/workflow`}>
                      Договор и выплаты →
                    </AppLink>
                  )}
                  <ClientDetailsEditor
                    key={`${row.id}-${row.full_name}-${row.phone}-${row.admin_note}`}
                    row={row}
                  />
                  {!row.workflow &&
                    row.current_status !== "paid" &&
                    row.current_status !== "rejected" && (
                      <ClientPayoutEditor
                        key={`${row.id}-${row.current_amount}-${row.payout_due_date}`}
                        row={row}
                      />
                    )}
                  <DeleteRecordButton
                    kind="clients"
                    id={row.id}
                    name={row.full_name}
                    onDeleted={() => setDeletedNotice(`Клиент «${row.full_name}» удалён`)}
                  />
                </article>
              ))}
            </div>
          )}
          {pagination}
        </>
      )}
    </>
  );
}

function ClientPayoutEditor({ row }: { row: ExistingClient }) {
  const [editing, setEditing] = useState(false);
  const [amount, setAmount] = useState(row.current_amount ?? "");
  const [dueDate, setDueDate] = useState(row.payout_due_date ?? "");
  const [saved, setSaved] = useState(false);
  const save = useUpdateClientPayout(row.id);

  function submit(event: FormEvent) {
    event.preventDefault();
    if (save.isPending) return;
    save.mutate(
      { current_amount: amount, payout_due_date: dueDate },
      {
        onSuccess: () => {
          setEditing(false);
          setSaved(true);
        },
      },
    );
  }

  return (
    <div className="client-payout-editor">
      {!editing ? (
        <>
          <button
            className="button secondary"
            type="button"
            onClick={() => {
              setSaved(false);
              setEditing(true);
            }}
          >
            {row.current_amount === null ? "Указать выплату" : "Изменить сумму и дату"}
          </button>
          {saved && (
            <p role="status" className="notice-success">
              Выплата сохранена
            </p>
          )}
        </>
      ) : (
        <form onSubmit={submit}>
          <fieldset className="client-deal-fields" disabled={save.isPending}>
            <legend>Выплата партнёру</legend>
            <Field
              label="К выплате партнёру, ₽"
              type="number"
              min="0.01"
              max="9999999999.99"
              step="0.01"
              required
              value={amount}
              onChange={(event) => setAmount(event.target.value)}
            />
            <Field
              label="Выплатить партнёру до"
              type="date"
              min="2000-01-01"
              max="2200-12-31"
              required
              value={dueDate}
              onChange={(event) => setDueDate(event.target.value)}
            />
            <p className="admin-form-help">Дата сохраняется независимо от одобрения начисления.</p>
            {save.isError && (
              <p className="alert" role="alert">
                {errorMessage(save.error)}
              </p>
            )}
            <div className="footer-actions">
              <button className="button" type="submit">
                {save.isPending ? "Сохраняем…" : "Сохранить"}
              </button>
              <button className="button secondary" type="button" onClick={() => setEditing(false)}>
                Отмена
              </button>
            </div>
          </fieldset>
        </form>
      )}
    </div>
  );
}

function ClientDetailsEditor({ row }: { row: ExistingClient }) {
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(row.full_name);
  const [phone, setPhone] = useState(row.phone ?? "");
  const [note, setNote] = useState(row.admin_note ?? "");
  const save = useUpdateClient(row.id);

  function submit(event: FormEvent) {
    event.preventDefault();
    if (save.isPending) return;
    save.mutate(
      { full_name: name.trim(), phone: phone.trim(), admin_note: note.trim() },
      {
        onSuccess: () => setEditing(false),
      },
    );
  }

  return (
    <div className="client-payout-editor">
      {!editing ? (
        <button className="button secondary" type="button" onClick={() => setEditing(true)}>
          Редактировать клиента
        </button>
      ) : (
        <form onSubmit={submit}>
          <fieldset className="client-deal-fields" disabled={save.isPending}>
            <legend>Данные клиента</legend>
            <Field
              label="ФИО клиента"
              required
              maxLength={200}
              value={name}
              onChange={(event) => setName(event.target.value)}
            />
            <Field
              label="Телефон клиента"
              type="tel"
              required
              maxLength={30}
              value={phone}
              onChange={(event) => setPhone(event.target.value)}
            />
            <label>
              Заметка
              <textarea
                rows={3}
                maxLength={2000}
                value={note}
                onChange={(event) => setNote(event.target.value)}
              />
            </label>
            {save.isError && (
              <p className="alert" role="alert">
                {errorMessage(save.error)}
              </p>
            )}
            <div className="footer-actions">
              <button className="button" type="submit">
                {save.isPending ? "Сохраняем…" : "Сохранить"}
              </button>
              <button className="button secondary" type="button" onClick={() => setEditing(false)}>
                Отмена
              </button>
            </div>
          </fieldset>
        </form>
      )}
    </div>
  );
}

function ClientFilterForm({
  filters,
  onApply,
}: {
  filters: ClientFilters;
  onApply: (filters: ClientFilters) => void;
}) {
  const [q, setQ] = useState(filters.q);
  const [agentId, setAgentId] = useState(filters.agentId);
  function apply(event: FormEvent) {
    event.preventDefault();
    onApply({ q: q.trim(), agentId, page: 1 });
  }
  return (
    <form className="client-list-filters" onSubmit={apply}>
      <Field
        label="Найти клиента по имени, телефону или сделке"
        value={q}
        onChange={(event) => setQ(event.target.value)}
      />
      <details className="client-filter-partner">
        <summary>
          {agentId === null ? "Партнёр: все · выбрать" : `Партнёр #${agentId} · изменить`}
        </summary>
        <PartnerSelector value={agentId} onChange={setAgentId} />
      </details>
      <div className="footer-actions">
        <button className="button" type="submit">
          Искать
        </button>
        <button
          className="button secondary"
          type="button"
          onClick={() => {
            setQ("");
            setAgentId(null);
            onApply({ q: "", agentId: null, page: 1 });
          }}
        >
          Сбросить фильтры
        </button>
      </div>
    </form>
  );
}
