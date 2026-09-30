import { useState, type FormEvent } from "react";

import type { Partner } from "./types";

interface NoteFormProps {
  partner: Partner;
  disabled: boolean;
  onSave: (id: number, note: string) => void;
}

export function NoteForm({ partner, disabled, onSave }: NoteFormProps) {
  const [note, setNote] = useState(partner.admin_note ?? "");

  function submit(event: FormEvent) {
    event.preventDefault();
    onSave(partner.id, note);
  }

  return (
    <form onSubmit={submit}>
      <input
        type="text"
        name="note"
        placeholder="Заметка"
        aria-label={`Заметка: ${partner.display_name || partner.email || partner.id}`}
        value={note}
        onChange={(event) => setNote(event.target.value)}
      />
      <button className="button secondary" type="submit" disabled={disabled}>
        Сохранить
      </button>
    </form>
  );
}

interface AccessActionsProps {
  partner: Partner;
  disabled: boolean;
  onBlock: (id: number, reason: string) => void;
  onUnblock: (id: number) => void;
}

/** Block (with a required reason) for an active partner, unblock for a blocked one. */
export function AccessActions({ partner, disabled, onBlock, onUnblock }: AccessActionsProps) {
  const [reason, setReason] = useState("");

  if (partner.is_admin) return <>—</>;

  if (!partner.is_active) {
    return (
      <form
        onSubmit={(event) => {
          event.preventDefault();
          onUnblock(partner.id);
        }}
      >
        <button className="button secondary" type="submit" disabled={disabled}>
          Разблокировать
        </button>
      </form>
    );
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    onBlock(partner.id, reason);
  }

  return (
    <form onSubmit={submit}>
      <input
        type="text"
        name="reason"
        placeholder="Причина блокировки"
        aria-label={`Причина блокировки: ${partner.display_name || partner.email || partner.id}`}
        required
        value={reason}
        onChange={(event) => setReason(event.target.value)}
      />
      <button className="button danger" type="submit" disabled={disabled}>
        Заблокировать
      </button>
    </form>
  );
}
