import { useState, type FormEvent } from "react";

import { useSession } from "@/features/session/useSession";
import { Field } from "@/shared/ui/Field";

interface CodeFormProps {
  submitLabel: string;
  autoFocus?: boolean;
  pending: boolean;
  /** Called with the entered code and a function that empties the field (after a failed try). */
  onSubmit: (code: string, clear: () => void) => void;
}

export function CodeForm({ submitLabel, autoFocus = false, pending, onSubmit }: CodeFormProps) {
  const { data: session } = useSession();
  const [code, setCode] = useState("");

  function submit(event: FormEvent) {
    event.preventDefault();
    onSubmit(code, () => setCode(""));
  }

  return (
    <form onSubmit={submit}>
      <Field
        label="Код из приложения"
        name="code"
        inputMode="numeric"
        pattern="[0-9]{6}"
        maxLength={6}
        required
        autoComplete="one-time-code"
        autoFocus={autoFocus}
        value={code}
        onChange={(event) => setCode(event.target.value)}
      />
      {/* The CSRF token comes with the session: no submit before it has loaded. */}
      <button className="button" type="submit" disabled={!session || pending}>
        {submitLabel}
      </button>
    </form>
  );
}
