import type { InputHTMLAttributes } from "react";

interface FieldProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
}

export function Field({ label, ...input }: FieldProps) {
  return (
    <label>
      {label}
      <input {...input} />
    </label>
  );
}
