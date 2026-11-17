import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiRequest } from "@/shared/api/client";
import { errorMessage } from "@/shared/api/errors";
import { AdminIcon } from "../AdminIcon";

type Kind = "partners" | "clients";
interface Preview {
  name: string;
  phone: string | null;
  email: string | null;
  client_count: number;
  reward_count: number;
  invited_partner_count: number;
  curator_client_count: number;
  can_delete: boolean;
  blocked_reason: string | null;
  token: string;
}
interface Props {
  kind: Kind;
  id: number;
  name: string;
  disabled?: boolean;
  onDeleted?: () => void;
}
export function DeleteRecordButton(props: Props) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button
        type="button"
        className="record-delete-trigger"
        disabled={props.disabled}
        aria-label={`Удалить ${props.kind === "partners" ? "партнёра" : "клиента"}: ${props.name}`}
        onClick={() => setOpen(true)}
      >
        <AdminIcon name="delete" /> Удалить
      </button>
      {open && <DeleteDialog {...props} onClose={() => setOpen(false)} />}
    </>
  );
}
function DeleteDialog({ kind, id, name, onClose, onDeleted }: Props & { onClose: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  const client = useQueryClient();
  const url = `/api/v1/site/admin/deletions/${kind}/${id}`;
  const query = useQuery({
    queryKey: ["admin", "deletion-preview", kind, id],
    queryFn: ({ signal }) => apiGet<Preview>(url, signal),
    retry: false,
    staleTime: 0,
  });
  const remove = useMutation({
    mutationFn: (token: string) => apiRequest("DELETE", url, { body: { token } }),
    onSuccess: () => {
      onClose();
      onDeleted?.();
      void client.invalidateQueries({ queryKey: ["admin"] });
    },
    onError: () => {
      void query.refetch();
    },
  });
  useEffect(() => {
    const element = ref.current;
    const previous = document.activeElement as HTMLElement | null;
    element?.showModal();
    return () => {
      element?.close();
      previous?.focus();
    };
  }, []);
  const data = query.data;
  const title = `delete-${kind}-${id}`;
  return (
    <dialog
      ref={ref}
      className="record-delete-dialog"
      aria-labelledby={title}
      onCancel={(event) => {
        event.preventDefault();
        if (!remove.isPending) onClose();
      }}
    >
      <header>
        <span className="record-delete-symbol">
          <AdminIcon name="delete" />
        </span>
        <h2 id={title}>{kind === "partners" ? "Удалить партнёра?" : "Удалить клиента?"}</h2>
      </header>
      <p className="record-delete-name">{data?.name || name}</p>
      {data && <p className="hint">{[data.email, data.phone].filter(Boolean).join(" · ")}</p>}
      {query.isPending && <p role="status">Проверяем связанные записи…</p>}
      {query.isError && (
        <p role="alert" className="alert">
          {errorMessage(query.error)}
        </p>
      )}
      {data && (
        <>
          <div className="record-delete-summary">
            <p>
              {kind === "partners"
                ? "Будет удалён аккаунт партнёра и все его клиенты."
                : "Будет удалена только эта запись клиента. Аккаунт партнёра и остальные клиенты сохранятся."}
            </p>
            <dl>
              <dt>Клиентов</dt>
              <dd>{data.client_count}</dd>
              <dt>Связанных начислений</dt>
              <dd>{data.reward_count}</dd>
            </dl>
            {data.invited_partner_count > 0 && (
              <p>
                Приглашённые партнёры ({data.invited_partner_count}) останутся в системе, связь с
                удаляемым куратором будет убрана.
              </p>
            )}
            {data.curator_client_count > 0 && (
              <p>
                У других клиентов ({data.curator_client_count}) будет убрана связь с этим куратором
                и его невыплаченные начисления. Сами клиенты сохранятся.
              </p>
            )}
          </div>
          <p>
            Сделки и контакты в Битриксе сохранятся. Удалённые записи на сайте восстановить нельзя.
          </p>
          {!data.can_delete && (
            <p className="alert" role="alert">
              {data.blocked_reason}
            </p>
          )}
        </>
      )}
      {remove.isError && (
        <p className="alert" role="alert">
          {errorMessage(remove.error)}
        </p>
      )}
      <footer className="footer-actions">
        <button
          type="button"
          className="button secondary"
          disabled={remove.isPending}
          onClick={onClose}
        >
          Отмена
        </button>
        <button
          type="button"
          className="button danger"
          disabled={!data?.can_delete || query.isFetching || remove.isPending}
          onClick={() => {
            if (data && !remove.isPending) remove.mutate(data.token);
          }}
        >
          {remove.isPending
            ? "Удаляем…"
            : kind === "partners"
              ? "Удалить партнёра и его клиентов"
              : "Удалить клиента"}
        </button>
      </footer>
    </dialog>
  );
}
