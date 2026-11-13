import { useRef, useState, type FormEvent } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { errorMessage } from "@/shared/api/errors";
import { usePageTitle } from "@/shared/hooks/usePageTitle";
import { Field } from "@/shared/ui/Field";
import { PageBack } from "@/shared/ui/PageBack";
import {
  clientsSearch,
  parseDealReference,
  positiveId,
  useAddClient,
  useFindDeal,
  useSearchBitrixClients,
  type DealSnapshot,
  type BitrixSearchResults,
} from "./api";
import { BitrixLink } from "./BitrixLink";
import { PartnerSelector } from "./PartnerSelector";

export function ClientEditorPage() {
  usePageTitle("Добавить действующего клиента");
  const [params] = useSearchParams();
  const initialAgent = positiveId(params.get("agent_id"));
  return <ClientForm key={initialAgent ?? "new"} initialAgent={initialAgent} />;
}

function ClientForm({ initialAgent }: { initialAgent: number | null }) {
  const navigate = useNavigate();
  const [agentId, setAgentId] = useState(initialAgent);
  const [dealId, setDealId] = useState("");
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [amount, setAmount] = useState("");
  const [note, setNote] = useState("");
  const [validation, setValidation] = useState("");
  const lookup = useFindDeal();
  const save = useAddClient();
  const [snapshot, setSnapshot] = useState<DealSnapshot | null>(null);
  const [lookupError, setLookupError] = useState("");
  const [finding, setFinding] = useState(false);
  const lookupToken = useRef(0);
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<BitrixSearchResults | null>(null);
  const [searchError, setSearchError] = useState("");
  const [searching, setSearching] = useState(false);
  const searchToken = useRef(0);
  const search = useSearchBitrixClients();

  async function findDeal(reference: string) {
    const token = ++lookupToken.current;
    if (!parseDealReference(reference)) {
      setLookupError("Укажите ID сделки или полную ссылку на сделку в Битрикс24.");
      setFinding(false);
      return;
    }
    setFinding(true);
    setSnapshot(null);
    setLookupError("");
    try {
      const deal = await lookup.mutateAsync(reference.trim());
      if (token !== lookupToken.current) return;
      setSnapshot(deal);
      setDealId(String(deal.deal_id));
      setName(deal.full_name ?? "");
      setPhone(deal.phone ?? "");
    } catch (error) {
      if (token === lookupToken.current) setLookupError(errorMessage(error));
    } finally {
      if (token === lookupToken.current) setFinding(false);
    }
  }

  async function searchClients(page = 1) {
    const token = ++searchToken.current;
    // Changing the search must also invalidate any unfinished candidate preview.
    ++lookupToken.current;
    setFinding(false);
    const q = query.trim();
    setResults(null);
    setSearchError("");
    if (q.length < 3 || q.length > 200) {
      setSearchError("Укажите ФИО: от 3 до 200 символов.");
      return;
    }
    setSearching(true);
    try {
      const data = await search.mutateAsync({ q, page });
      if (token === searchToken.current) setResults(data);
    } catch (error) {
      if (token === searchToken.current) setSearchError(errorMessage(error));
    } finally {
      if (token === searchToken.current) setSearching(false);
    }
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    if (finding || save.isPending) return;
    const normalizedId = parseDealReference(dealId);
    if (agentId === null || !normalizedId || !name.trim()) {
      setValidation("Выберите партнёра и укажите ID или ссылку на сделку и ФИО клиента.");
      return;
    }
    if (!/^[1-9]\d*$/.test(dealId.trim()) && !snapshot) {
      setValidation("Сначала нажмите «Найти сделку», чтобы проверить ссылку.");
      return;
    }
    if (amount !== "" && (!Number.isFinite(Number(amount)) || Number(amount) <= 0)) {
      setValidation("Укажите положительную сумму в рублях или оставьте поле пустым.");
      return;
    }
    setValidation("");
    save.mutate(
      {
        agent_id: agentId,
        deal_id: snapshot ? String(snapshot.deal_id) : normalizedId,
        full_name: name.trim(),
        phone: phone.trim(),
        current_amount: amount === "" ? null : amount,
        admin_note: note.trim(),
      },
      {
        onSuccess: () =>
          navigate(`/admin/clients${clientsSearch({ q: "", agentId, page: 1 })}`, {
            state: {
              info:
                amount === ""
                  ? "Действующий клиент добавлен без начального остатка к выплате."
                  : "Действующий клиент добавлен. Текущая выплата ожидает обработки.",
            },
          }),
      },
    );
  }

  return (
    <>
      <PageBack to={`/admin/clients${clientsSearch({ q: "", agentId: initialAgent, page: 1 })}`}>
        ← Действующие клиенты
      </PageBack>
      <section className="card admin-client-form">
        <p className="eyebrow">Действующие клиенты</p>
        <h1>Добавить клиента</h1>
        <div className="client-info" role="note">
          <p>Выберите партнёра и укажите существующую сделку в Битрикс24.</p>
        </div>
        <form onSubmit={submit}>
          <PartnerSelector value={agentId} onChange={setAgentId} disabled={save.isPending} />
          <fieldset className="client-deal-fields" disabled={save.isPending}>
            <legend>Существующая сделка</legend>
            <div className="client-search-row">
              <Field
                label="ФИО для поиска в Битриксе"
                value={query}
                maxLength={200}
                onChange={(event) => {
                  setQuery(event.target.value);
                  ++searchToken.current;
                  ++lookupToken.current;
                  setSearching(false);
                  setFinding(false);
                  setResults(null);
                  setSearchError("");
                }}
              />
              <button
                className="button secondary"
                type="button"
                disabled={searching}
                onClick={() => void searchClients()}
              >
                {searching ? "Ищем клиента…" : "Найти клиента в Битриксе"}
              </button>
            </div>
            {searchError && (
              <p className="alert" role="alert">
                {searchError}
              </p>
            )}
            {results && (
              <section aria-label="Результаты поиска в Битриксе" aria-live="polite">
                {results.rows.length === 0 && <p>Клиенты не найдены. Уточните ФИО.</p>}
                <div className="client-bitrix-results">
                  {results.rows.map((row) => (
                    <article className="client-bitrix-candidate" key={`${row.kind}-${row.id}`}>
                      <h2>{row.full_name || "ФИО не указано"}</h2>
                      <p>{row.phone || "Телефон не указан"}</p>
                      <p>
                        {row.kind === "deal" ? "Сделка" : "Лид"} #{row.id}: {row.title}
                      </p>
                      <p>Воронка: {row.category_label || "Не указана"}</p>
                      <p>
                        Этап:{" "}
                        {row.stage_label && row.stage_label !== row.stage_code
                          ? row.stage_label
                          : "Название этапа недоступно"}
                      </p>
                      <div className="footer-actions">
                        <BitrixLink url={row.url} />
                        {row.kind === "deal" && (
                          <button
                            className="button secondary"
                            type="button"
                            onClick={() => {
                              setDealId(String(row.id));
                              void findDeal(String(row.id));
                            }}
                          >
                            Выбрать сделку
                          </button>
                        )}
                      </div>
                      {row.kind === "lead" && <p className="hint">Для привязки нужна сделка</p>}
                    </article>
                  ))}
                </div>
                <div className="client-selector-pages">
                  {results.page > 1 && (
                    <button
                      className="button secondary"
                      type="button"
                      onClick={() => void searchClients(results.page - 1)}
                    >
                      Предыдущие результаты
                    </button>
                  )}
                  {results.has_more && (
                    <button
                      className="button secondary"
                      type="button"
                      onClick={() => void searchClients(results.page + 1)}
                    >
                      Следующие результаты
                    </button>
                  )}
                </div>
              </section>
            )}
            <div className="client-search-row">
              <Field
                label="ID сделки в Битрикс24 или ссылка"
                name="deal_id"
                required
                value={dealId}
                onChange={(event) => {
                  setDealId(event.target.value);
                  ++lookupToken.current;
                  setFinding(false);
                  setSnapshot(null);
                  setLookupError("");
                }}
              />
              <button
                className="button secondary"
                type="button"
                disabled={!dealId.trim()}
                onClick={() => void findDeal(dealId)}
              >
                {finding ? "Ищем сделку…" : "Найти сделку"}
              </button>
            </div>
            {lookupError && (
              <p className="alert" role="alert">
                {lookupError} Можно заполнить ФИО и телефон вручную.
              </p>
            )}
            {snapshot && (
              <div className="client-deal-preview" aria-label="Данные сделки из Битрикс24">
                <h2>Сделка #{snapshot.deal_id}</h2>
                <BitrixLink url={snapshot.deal_url} />
                <dl>
                  <div>
                    <dt>Этап сделки</dt>
                    <dd>
                      {snapshot.stage_label && snapshot.stage_label !== snapshot.stage_code
                        ? snapshot.stage_label
                        : "Название этапа недоступно"}
                    </dd>
                  </div>
                  <div>
                    <dt>ФИО в сделке</dt>
                    <dd>{snapshot.full_name || "Не указано"}</dd>
                  </div>
                  <div>
                    <dt>Телефон в сделке</dt>
                    <dd>{snapshot.phone || "Не указан"}</dd>
                  </div>
                </dl>
              </div>
            )}
            <p className="hint">Проверьте ФИО и телефон клиента.</p>
            <div className="admin-form-grid">
              <Field
                label="ФИО клиента"
                name="full_name"
                required
                maxLength={200}
                value={name}
                onChange={(event) => setName(event.target.value)}
              />
              <Field
                label="Телефон клиента"
                name="phone"
                type="tel"
                maxLength={30}
                value={phone}
                onChange={(event) => setPhone(event.target.value)}
              />
              <Field
                label="К выплате партнёру"
                name="current_amount"
                type="number"
                min="0.01"
                step="0.01"
                placeholder="Необязательно, ₽"
                value={amount}
                onChange={(event) => setAmount(event.target.value)}
              />
              <p className="admin-form-help">
                Сумма в рублях, больше нуля. Оставьте пустой, если сейчас выплачивать нечего.
              </p>
              <label className="admin-form-wide">
                Заметка
                <textarea
                  name="admin_note"
                  rows={3}
                  maxLength={2000}
                  value={note}
                  onChange={(event) => setNote(event.target.value)}
                />
              </label>
            </div>
          </fieldset>
          {validation && (
            <p className="alert" role="alert">
              {validation}
            </p>
          )}
          {save.isError && (
            <p className="alert" role="alert">
              {errorMessage(save.error)}
            </p>
          )}
          <div className="footer-actions">
            <button className="button" type="submit" disabled={save.isPending || finding}>
              {save.isPending ? "Добавляем…" : "Добавить клиента"}
            </button>
          </div>
        </form>
      </section>
    </>
  );
}
