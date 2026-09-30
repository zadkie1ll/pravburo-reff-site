import type { TextareaHTMLAttributes } from "react";

interface TextAreaFieldProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label: string;
}

export function TextAreaField({ label, ...textarea }: TextAreaFieldProps) {
  return (
    <label>
      {label}
      <textarea {...textarea} />
    </label>
  );
}
