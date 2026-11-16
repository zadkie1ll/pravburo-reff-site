import { useState, type FormEvent } from "react";
import { useParams } from "react-router-dom";
import { usePageTitle } from "@/shared/hooks/usePageTitle";
import { PageBack } from "@/shared/ui/PageBack";
import { PageError, PageLoader } from "@/shared/ui/PageState";
import { Field } from "@/shared/ui/Field";
import {
  useClientWorkflow,
  useSaveClientWorkflow,
  usePayWorkflow,
  type ClientWorkflow,
} from "./api";
import { WorkflowFields, readWorkflow, workflowError, rubles, dateLabel } from "./WorkflowFields";

const stageStatuses: Record<string, string> = {
  paid: "Выплачено",
  ready: "К выплате",
  waiting: "Ожидаем оплату клиента",
  none: "Не предусмотрено",
  rejected: "Отклонено",
};
export function ClientWorkflowPage() {
  usePageTitle("Договор и выплаты");
  const id = Number(useParams().id);
  const query = useClientWorkflow(id);
  const save = useSaveClientWorkflow(id);
  const pay = usePayWorkflow(id);
  const [notice, setNotice] = useState("");
  if (query.isPending) return <PageLoader />;
  if (query.isError) return <PageError />;
  const { workflow, full_name: name, agent_id: agentId } = query.data;
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setNotice("");
    save.mutate(readWorkflow(event.currentTarget, workflow?.version ?? 0), {
      onSuccess: () => setNotice("Договор и выплаты сохранены"),
    });
  }
  const busy = save.isPending || pay.isPending;
  return (
    <>
      <PageBack to="/admin/clients">← Действующие клиенты</PageBack>
      <section className="card">
        <p className="eyebrow">Действующий клиент</p>
        <h1>{name}</h1>
        <p>Договор и выплаты</p>
        {workflow && (
          <div className="settlement-summary">
            <strong>{workflow.status_label}</strong>
            <span>Всего к выплате: {rubles(workflow.outstanding)}</span>
          </div>
        )}
      </section>
      {notice && (
        <p role="status" className="notice-success">
          {notice}
        </p>
      )}
      {(save.error || pay.error) && (
        <p className="alert" role="alert">
          {workflowError(save.error || pay.error)}
        </p>
      )}
      {workflow?.input.contract_date && (
        <section className="settlement-stage-grid" aria-label="Состояние выплат">
          {workflow.stages.map((stage) => (
            <article className="settlement-stage" key={stage.key}>
              <h2>{stage.label}</h2>
              <span className={`settlement-badge ${stage.status}`}>
                {stageStatuses[stage.status] ?? stage.status}
              </span>
              <p className="settlement-amount">{rubles(stage.amount)}</p>
              {stage.recipient && <p>Получатель: {stage.recipient}</p>}
              <dl>
                <dt>Срок выплаты</dt>
                <dd>{dateLabel(stage.due_on)}</dd>
                <dt>Выплачено</dt>
                <dd>
                  {stage.paid_on
                    ? dateLabel(stage.paid_on)
                    : stage.status === "none"
                      ? "Не требуется"
                      : "Ещё не выплачено"}
                </dd>
              </dl>
              {stage.historical && <p className="hint">Выплачено до переноса</p>}
              {stage.status === "ready" &&
                (stage.key !== "bonus" ||
                  workflow.stages.find((item) => item.key === "main")?.status !== "ready") && (
                  <PaymentButton
                    busy={busy}
                    kind={stage.key}
                    workflow={workflow}
                    onPay={(date) => {
                      if (
                        window.confirm(
                          "Отметить выплату произведённой? Партнёру уйдёт уведомление.",
                        )
                      )
                        pay.mutate(
                          { kind: stage.key, version: workflow.version, paid_on: date },
                          { onSuccess: () => setNotice("Выплата отмечена") },
                        );
                    }}
                  />
                )}
              {stage.key === "bonus" &&
                stage.status === "ready" &&
                workflow.stages.find((item) => item.key === "main")?.status === "ready" && (
                  <p className="hint">Отмечается вместе с основной выплатой</p>
                )}
            </article>
          ))}
        </section>
      )}
      <section className="card mt-20">
        <details className="settlement-settings" open={workflow ? undefined : true}>
          <summary>Договор и расчёт выплат — изменить</summary>
          <form key={workflow?.version ?? "new"} onSubmit={submit} className="settlement-form">
            <fieldset disabled={busy} className="settlement-form-body">
              <WorkflowFields agentId={agentId} workflow={workflow} />
              <div className="footer-actions">
                <button type="submit" className="button">
                  {save.isPending ? "Сохраняем…" : "Сохранить договор и выплаты"}
                </button>
              </div>
            </fieldset>
          </form>
        </details>
      </section>
    </>
  );
}
function PaymentButton({
  busy,
  kind,
  workflow,
  onPay,
}: {
  busy: boolean;
  kind: string;
  workflow: ClientWorkflow;
  onPay: (date: string) => void;
}) {
  const [date, setDate] = useState(
    new Intl.DateTimeFormat("sv-SE", { timeZone: "Europe/Moscow" }).format(new Date()),
  );
  return (
    <form
      className="settlement-pay"
      onSubmit={(event) => {
        event.preventDefault();
        onPay(date);
      }}
    >
      <Field
        label="Фактическая дата выплаты"
        type="date"
        required
        min={workflow.input.contract_date ?? undefined}
        value={date}
        onChange={(event) => setDate(event.target.value)}
        disabled={busy}
      />
      <button className="button" type="submit" disabled={busy}>
        {kind === "main"
          ? workflow.stages.some((stage) => stage.key === "bonus" && stage.status === "ready")
            ? "Основная и бонус выплачены"
            : "Основная выплачена"
          : kind === "curator"
            ? "Куратор получил"
            : kind === "bonus"
              ? "Бонус выплачен"
              : "Аванс выплачен"}
      </button>
    </form>
  );
}
