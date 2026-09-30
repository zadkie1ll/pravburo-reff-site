import { useState, type FormEvent } from "react";

import { Field } from "@/shared/ui/Field";
import { SelectField } from "@/shared/ui/SelectField";

import { filtersToQuery } from "./api";
import type { Option, PayoutFilters } from "./types";

interface PayoutFilterFormProps {
  applied: PayoutFilters;
  rewardTypes: Option[];
  statuses: Option[];
  onApply: (filters: PayoutFilters) => void;
}

export function PayoutFilterForm({
  applied,
  rewardTypes,
  statuses,
  onApply,
}: PayoutFilterFormProps) {
  const [draft, setDraft] = useState(applied);
  const pdfQuery = filtersToQuery(applied);

  function submit(event: FormEvent) {
    event.preventDefault();
    onApply(draft);
  }

  return (
    <section className="card">
      <form className="filter-row" onSubmit={submit}>
        <Field
          label="Месяц"
          type="month"
          name="month"
          value={draft.month}
          onChange={(event) => setDraft({ ...draft, month: event.target.value })}
        />
        <SelectField
          label="Тип выплаты"
          name="reward_type"
          options={rewardTypes}
          value={draft.reward_type}
          onChange={(event) => setDraft({ ...draft, reward_type: event.target.value })}
        />
        <SelectField
          label="Статус"
          name="status"
          options={statuses}
          value={draft.status}
          onChange={(event) => setDraft({ ...draft, status: event.target.value })}
        />
        <button className="button" type="submit">
          Показать
        </button>
        {/* The PDF follows the filters that are applied (shown in the table), not the draft. */}
        <a
          className="button secondary"
          href={`/payouts/export.pdf${pdfQuery ? `?${pdfQuery}` : ""}`}
        >
          Экспорт в PDF
        </a>
      </form>
    </section>
  );
}
