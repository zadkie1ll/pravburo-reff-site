import { useState, type FormEvent } from "react";

import { Field } from "@/shared/ui/Field";
import { SelectField } from "@/shared/ui/SelectField";

import type { ListFilters } from "./listFilters";

interface Option {
  value: string;
  label: string;
}

interface SearchFilterFormProps {
  title: string;
  searchLabel: string;
  statusLabel: string;
  statusOptions: Option[];
  applied: ListFilters;
  totalCount: number;
  onApply: (filters: ListFilters) => void;
}

/** Header card of an admin list: title, search box, status filter and the total. */
export function SearchFilterForm({
  title,
  searchLabel,
  statusLabel,
  statusOptions,
  applied,
  totalCount,
  onApply,
}: SearchFilterFormProps) {
  const [q, setQ] = useState(applied.q);
  const [status, setStatus] = useState(applied.status);

  function submit(event: FormEvent) {
    event.preventDefault();
    // A new search starts from the first page.
    onApply({ q: q.trim(), status, page: 1 });
  }

  return (
    <section className="card">
      <p className="eyebrow">Администратор</p>
      <h1>{title}</h1>
      <form onSubmit={submit}>
        <Field
          label={searchLabel}
          type="text"
          name="q"
          autoFocus
          value={q}
          onChange={(event) => setQ(event.target.value)}
        />
        <SelectField
          label={statusLabel}
          name="status"
          options={statusOptions}
          value={status}
          onChange={(event) => setStatus(event.target.value)}
        />
        <button className="button button-spaced" type="submit">
          Искать
        </button>
      </form>
      <p>Всего: {totalCount}</p>
    </section>
  );
}
