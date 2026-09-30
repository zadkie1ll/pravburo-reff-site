import { useState, type FormEvent } from "react";

import { errorMessage } from "@/shared/api/errors";
import { Field } from "@/shared/ui/Field";

import { useBeginEmailChange, useConfirmEmailChange } from "./api";
import type { NoticeState } from "@/shared/ui/Notice";
import type { Profile } from "./types";

interface EmailChangeProps {
  profile: Profile;
  onNotice: (notice: NoticeState) => void;
}

/** Two steps: new address + password, then the code that was sent to the new address. */
export function EmailChange({ profile, onNotice }: EmailChangeProps) {
  const begin = useBeginEmailChange();
  const confirm = useConfirmEmailChange();
  const [newEmail, setNewEmail] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");

  const fail = (error: unknown) => onNotice({ kind: "error", text: errorMessage(error) });

  function submitAddress(event: FormEvent) {
    event.preventDefault();
    begin.mutate(
      { new_email: newEmail, current_password: password },
      {
        onSuccess: ({ info }) => {
          setPassword("");
          onNotice({ kind: "success", text: info });
        },
        onError: fail,
      },
    );
  }

  function submitCode(event: FormEvent) {
    event.preventDefault();
    confirm.mutate(code, {
      onSuccess: ({ info }) => {
        setCode("");
        setNewEmail("");
        onNotice({ kind: "success", text: info });
      },
      onError: (error) => {
        setCode("");
        fail(error);
      },
    });
  }

  if (profile.pending_email) {
    return (
      <>
        <p>
          Код отправлен на <strong>{profile.pending_email}</strong>. Введите его, чтобы подтвердить
          смену почты.
        </p>
        <form className="lead-form" onSubmit={submitCode}>
          <Field
            label="Код из письма"
            name="code"
            maxLength={6}
            required
            autoFocus
            autoComplete="one-time-code"
            value={code}
            onChange={(event) => setCode(event.target.value)}
          />
          <button className="button" type="submit" disabled={confirm.isPending}>
            Подтвердить почту
          </button>
        </form>
      </>
    );
  }

  return (
    <>
      <p>
        Текущая почта: <strong>{profile.email || "Не указана"}</strong>
      </p>
      <form className="lead-form" onSubmit={submitAddress}>
        <Field
          label="Новая почта"
          type="email"
          name="new_email"
          maxLength={254}
          required
          autoComplete="email"
          value={newEmail}
          onChange={(event) => setNewEmail(event.target.value)}
        />
        <Field
          label="Текущий пароль"
          type="password"
          name="current_password"
          required
          autoComplete="current-password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
        />
        <button className="button" type="submit" disabled={begin.isPending}>
          Сменить почту
        </button>
      </form>
    </>
  );
}
