import { useState, type FormEvent } from "react";

import { Field } from "@/shared/ui/Field";
import { TextAreaField } from "@/shared/ui/TextAreaField";

import type { FaqEntry, MoveDirection } from "./types";

interface FaqEntryCardProps {
  entry: FaqEntry;
  isFirst: boolean;
  isLast: boolean;
  disabled: boolean;
  onSave: (id: number, content: { question: string; answer: string }) => void;
  onMove: (id: number, direction: MoveDirection) => void;
  onDelete: (id: number) => void;
}

export function FaqEntryCard({
  entry,
  isFirst,
  isLast,
  disabled,
  onSave,
  onMove,
  onDelete,
}: FaqEntryCardProps) {
  const [question, setQuestion] = useState(entry.question);
  const [answer, setAnswer] = useState(entry.answer);

  function submit(event: FormEvent) {
    event.preventDefault();
    onSave(entry.id, { question, answer });
  }

  function remove() {
    if (window.confirm("Удалить вопрос?")) onDelete(entry.id);
  }

  return (
    <section className="card">
      <form onSubmit={submit}>
        <Field
          label="Вопрос"
          type="text"
          name="question"
          maxLength={300}
          required
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
        />
        <TextAreaField
          label="Ответ"
          name="answer"
          rows={3}
          required
          value={answer}
          onChange={(event) => setAnswer(event.target.value)}
        />
        <button className="button secondary button-spaced" type="submit" disabled={disabled}>
          Сохранить
        </button>
      </form>
      <div className="footer-actions mt-14">
        <div>
          <button
            className="text-button"
            type="button"
            disabled={isFirst || disabled}
            onClick={() => onMove(entry.id, "up")}
          >
            ↑ Выше
          </button>{" "}
          <button
            className="text-button"
            type="button"
            disabled={isLast || disabled}
            onClick={() => onMove(entry.id, "down")}
          >
            ↓ Ниже
          </button>
        </div>
        <button className="button danger" type="button" disabled={disabled} onClick={remove}>
          Удалить
        </button>
      </div>
    </section>
  );
}
