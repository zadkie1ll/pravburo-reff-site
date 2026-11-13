import { useState, type FormEvent } from "react";
import { useSearchParams } from "react-router-dom";
import { useInfoFromNavigation } from "@/features/auth/useInfoFromNavigation";
import { usePageTitle } from "@/shared/hooks/usePageTitle";
import { AppLink } from "@/shared/ui/AppLink";
import { Field } from "@/shared/ui/Field";
import { PageBack } from "@/shared/ui/PageBack";
import { Pagination } from "@/shared/ui/Pagination";
import { PageError, PageLoader } from "@/shared/ui/PageState";
import { clientsSearch, positiveId, useClients, type ClientFilters } from "./api";
import { BitrixLink } from "./BitrixLink";
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
      {info && (
        <p className="notice-success" role="status">
          {info}
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
                      <dt>Осталось выплатить сейчас</dt>
                      <dd>{money(row.current_amount)}</dd>
                    </div>
                    <div>
                      <dt>Статус текущей выплаты</dt>
                      <dd>
                        {row.current_status
                          ? (statuses[row.current_status] ?? row.current_status)
                          : "Не указан"}
                      </dd>
                    </div>
                    <div>
                      <dt>Добавлен</dt>
                      <dd>{row.created_at_label}</dd>
                    </div>
                  </dl>
                  {row.admin_note && <p className="partner-note-preview">{row.admin_note}</p>}
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
