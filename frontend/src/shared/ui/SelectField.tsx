import type { SelectHTMLAttributes } from "react";

interface Option {
  value: string;
  label: string;
}

interface SelectFieldProps extends SelectHTMLAttributes<HTMLSelectElement> {
  label: string;
  options: Option[];
  /** Label of the empty "no filter" choice; null means the field has no empty choice. */
  emptyLabel?: string | null;
}

export function SelectField({ label, options, emptyLabel = "Все", ...select }: SelectFieldProps) {
  return (
    <label>
      {label}
      <select {...select}>
        {emptyLabel !== null && <option value="">{emptyLabel}</option>}
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}
