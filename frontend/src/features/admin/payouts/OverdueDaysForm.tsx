import { useState, type FormEvent } from "react";

import { Field } from "@/shared/ui/Field";

interface OverdueDaysFormProps {
  days: number;
  disabled: boolean;
  onSave: (days: number) => void;
}

export function OverdueDaysForm({ days, disabled, onSave }: OverdueDaysFormProps) {
  const [value, setValue] = useState(String(days));

  function submit(event: FormEvent) {
    event.preventDefault();
    onSave(Number(value));
  }

  return (
    <form className="filter-row" onSubmit={submit}>
      <Field
        label="Просрочка через, дней"
        type="number"
        name="overdue_days"
        min={1}
        required
        value={value}
        onChange={(event) => setValue(event.target.value)}
      />
      <button className="button secondary" type="submit" disabled={disabled}>
        Сохранить
      </button>
    </form>
  );
}
