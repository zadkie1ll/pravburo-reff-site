import { useState, type FormEvent } from "react";

import { errorMessage } from "@/shared/api/errors";
import { Field } from "@/shared/ui/Field";
import { Notice } from "@/shared/ui/Notice";

import { useSaveRates } from "./api";
import type { Rate } from "./types";

export function RatesForm({ rates }: { rates: Rate[] }) {
  const save = useSaveRates();
  const [amounts, setAmounts] = useState<Record<number, string>>(
    Object.fromEntries(rates.map((rate) => [rate.level, rate.amount])),
  );

  function submit(event: FormEvent) {
    event.preventDefault();
    save.mutate(amounts);
  }

  return (
    <>
      {save.isError && <Notice notice={{ kind: "error", text: errorMessage(save.error) }} />}
      {save.isSuccess && <Notice notice={{ kind: "success", text: "Суммы сохранены" }} />}
      <form onSubmit={submit}>
        {rates.map((rate) => (
          <Field
            key={rate.level}
            label={rate.label}
            type="number"
            step="0.01"
            min="0"
            name={`amount_${rate.level}`}
            required
            value={amounts[rate.level] ?? ""}
            onChange={(event) => setAmounts({ ...amounts, [rate.level]: event.target.value })}
          />
        ))}
        <button className="button button-spaced" type="submit" disabled={save.isPending}>
          Сохранить
        </button>
      </form>
    </>
  );
}
