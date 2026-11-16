import { useState } from "react";
import { ApiError } from "@/shared/api/client";
import { errorMessage } from "@/shared/api/errors";
import { Field } from "@/shared/ui/Field";
import { useWorkflowDefaults, type ClientWorkflow, type WorkflowInput } from "./api";

export function workflowError(error: unknown) {
  if (error instanceof ApiError && Object.keys(error.fields).length) {
    return Object.values(error.fields)
      .map((text) => text.replace(/^Value error, /, ""))
      .join(". ");
  }
  return errorMessage(error);
}
export const dateLabel = (value: string | null) =>
  value ? value.split("-").reverse().join(".") : "Не указан";
export const rubles = (value: string) =>
  new Intl.NumberFormat("ru-RU", { style: "currency", currency: "RUB" }).format(Number(value));
export function readWorkflow(form: HTMLFormElement, version = 0): WorkflowInput {
  const data = new FormData(form);
  const text = (key: string) => String(data.get(`wf_${key}`) ?? "");
  const optional = (key: string) => text(key) || null;
  return {
    version,
    contract_status: text("contract_status") as WorkflowInput["contract_status"],
    contract_date: optional("contract_date"),
    first_payment: text("first_payment") || "0",
    deposit_paid_on: optional("deposit_paid_on"),
    paid_in_full: data.has("wf_paid_in_full"),
    advance_amount: text("advance_amount") || "0",
    main_amount: text("main_amount") || "0",
    curator_amount: text("curator_amount") || "0",
    advance_due_on: optional("advance_due_on"),
    main_due_on: optional("main_due_on"),
    advance_paid_on: optional("advance_paid_on"),
    main_paid_on: optional("main_paid_on"),
    curator_paid_on: optional("curator_paid_on"),
  };
}

export function WorkflowFields({
  agentId,
  workflow,
  firstPayment = "0",
  paidInFull = false,
}: {
  agentId: number | null;
  workflow?: ClientWorkflow | null;
  firstPayment?: string;
  paidInFull?: boolean;
}) {
  const initial = workflow?.input;
  const [contractStatus, setContractStatus] = useState(
    initial?.contract_status ?? (initial?.contract_date ? "signed" : "not_signed"),
  );
  const dated = contractStatus === "signed";
  const [contractDate, setContractDate] = useState(initial?.contract_date ?? "");
  const keepAmounts =
    initial &&
    (initial.contract_date ||
      Number(initial.advance_amount) > 0 ||
      Number(initial.main_amount) > 0);
  const defaults = useWorkflowDefaults(keepAmounts ? null : agentId, dated ? contractDate : "");
  const values = keepAmounts ? initial : defaults.data;
  const curator = workflow?.curator_name ?? defaults.data?.curator_name;
  const stage = (key: string) => workflow?.stages.find((item) => item.key === key);
  const locked = (key: string) => ["paid", "rejected"].includes(stage(key)?.status ?? "");
  const amount = (key: "advance" | "main" | "curator") => (
    <Field
      key={`${key}-${values?.[`${key}_amount`]}`}
      label={
        key === "advance"
          ? "Аванс агенту, ₽"
          : key === "main"
            ? "Основная сумма агенту, ₽"
            : "Выплата куратору, ₽"
      }
      name={`wf_${key}_amount`}
      type="number"
      min="0"
      max="9999999999.99"
      step="0.01"
      required
      readOnly={locked(key)}
      defaultValue={values?.[`${key}_amount`] ?? ""}
    />
  );
  const history = (key: "advance" | "main" | "curator", label: string) => {
    const current = stage(key);
    if (current?.reward_id)
      return (
        <p className="hint">
          {current.paid_on
            ? `Выплачено ${dateLabel(current.paid_on)}`
            : "Начисление создано. Отметить выплату можно в блоке ниже."}
        </p>
      );
    return (
      <Field
        label={label}
        name={`wf_${key}_paid_on`}
        type="date"
        readOnly={locked(key)}
        min={contractDate || "2000-01-01"}
        defaultValue={initial?.[`${key}_paid_on`] ?? ""}
      />
    );
  };
  return (
    <div className="settlement-fields">
      {!workflow && (
        <div className="client-info">
          Переносите действующего клиента? Укажите даты уже сделанных выплат в блоках ниже.
          Оставшиеся выплаты появятся в списке к оплате.
        </div>
      )}
      <fieldset className="settlement-block">
        <legend>Договор и оплаты клиента</legend>
        <p className="admin-form-help">Здесь — деньги, которые клиент внёс компании.</p>
        <div className="admin-form-grid">
          <label>
            Договор
            <select
              name="wf_contract_status"
              value={contractStatus}
              onChange={(event) =>
                setContractStatus(
                  event.target.value as NonNullable<WorkflowInput["contract_status"]>,
                )
              }
            >
              <option value="not_signed">Договор не заключён</option>
              <option value="date_unknown">Договор подписан, дата неизвестна</option>
              <option value="signed">Дата договора известна</option>
            </select>
          </label>
          {dated && (
            <Field
              label="Дата договора"
              name="wf_contract_date"
              type="date"
              min="2000-01-01"
              max="2199-12-31"
              required
              value={contractDate}
              onChange={(event) => setContractDate(event.target.value)}
            />
          )}
          <Field
            label="Внесено клиентом, ₽"
            name="wf_first_payment"
            type="number"
            min="0"
            step="0.01"
            required
            defaultValue={initial?.first_payment ?? firstPayment}
          />
          {contractStatus !== "not_signed" && (
            <>
              <Field
                label="Депозит оплачен — дата"
                name="wf_deposit_paid_on"
                type="date"
                min={contractDate || "2000-01-01"}
                defaultValue={initial?.deposit_paid_on ?? ""}
              />
              <label className="settlement-check">
                <input
                  type="checkbox"
                  name="wf_paid_in_full"
                  defaultChecked={initial?.paid_in_full ?? paidInFull}
                />
                100% оплата первым платежом
              </label>
            </>
          )}
        </div>
      </fieldset>
      {!dated && (
        <div className="client-info" role="status">
          {contractStatus === "not_signed"
            ? "Клиент будет закреплён за партнёром без договора. Начислений и сроков выплат пока не будет."
            : "Связь с партнёром и сведения об оплатах сохранятся. Укажите дату договора позже, чтобы рассчитать выплаты."}
        </div>
      )}
      {dated && (
        <>
          {!keepAmounts && (
            <div role="status" className="client-info">
              {!agentId ? (
                "Выберите партнёра, чтобы подтянуть суммы и куратора."
              ) : !contractDate ? (
                "Укажите дату договора, чтобы подтянуть суммы выплат."
              ) : defaults.isError ? (
                workflowError(defaults.error)
              ) : !values ? (
                "Загружаем суммы выплат…"
              ) : (
                <>
                  <span>Суммы загружены из настроек. </span>
                  <span>
                    Уровень:{" "}
                    {
                      (
                        {
                          start: "Старт",
                          active: "Актив",
                          pro: "Про",
                          expert: "Эксперт",
                        } as Record<string, string>
                      )[defaults.data?.level ?? "start"]
                    }
                    .{" "}
                  </span>
                  {defaults.data?.agent_phone && (
                    <span>Телефон агента: {defaults.data.agent_phone}.</span>
                  )}
                </>
              )}
            </div>
          )}
          <fieldset className="settlement-block">
            <legend>Аванс агенту</legend>
            <p className="admin-form-help">
              Доступен после поступления от клиента минимум 8 000 ₽. Срок — 5 рабочих дней от даты
              договора (пн–пт).
            </p>
            <div className="admin-form-grid">
              {amount("advance")}
              <Field
                label="Срок аванса — изменить вручную"
                name="wf_advance_due_on"
                type="date"
                defaultValue={initial?.advance_due_on ?? ""}
                readOnly={locked("advance")}
              />
            </div>
            <details className="settlement-history">
              <summary>Аванс уже выплачен до переноса</summary>
              {history("advance", "Аванс выплачен — дата")}
            </details>
          </fieldset>
          <fieldset className="settlement-block">
            <legend>Основная выплата</legend>
            <p className="admin-form-help">
              Срок — 15 рабочих дней после оплаты депозита (пн–пт). Бонус 100% — 3 000 ₽ при полной
              оплате первым платежом.
            </p>
            <div className="admin-form-grid">
              {amount("main")}
              <Field
                label="Срок основной выплаты — изменить вручную"
                name="wf_main_due_on"
                type="date"
                defaultValue={initial?.main_due_on ?? ""}
                readOnly={locked("main")}
              />
            </div>
            <details className="settlement-history">
              <summary>Основная уже выплачена до переноса</summary>
              {history("main", "Основная выплачена — дата")}
            </details>
          </fieldset>
          <fieldset className="settlement-block">
            <legend>Куратор</legend>
            <p>{curator || "У выбранного партнёра нет куратора"}</p>
            {(workflow?.curator_phone ?? defaults.data?.curator_phone) && (
              <p className="hint">
                Телефон куратора: {workflow?.curator_phone ?? defaults.data?.curator_phone}
              </p>
            )}
            {curator ? (
              <>
                <div className="admin-form-grid">{amount("curator")}</div>
                <details className="settlement-history">
                  <summary>Куратор уже получил выплату до переноса</summary>
                  {history("curator", "Куратор получил — дата")}
                </details>
              </>
            ) : (
              <input type="hidden" name="wf_curator_amount" value="0" />
            )}
          </fieldset>
          <p className="admin-form-help">
            Сохранение создаёт текущие начисления по заполненным условиям. Уже выплаченное до
            переноса сохраняется только как история.
          </p>
        </>
      )}
    </div>
  );
}
