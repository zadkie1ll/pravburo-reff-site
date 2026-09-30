import { useState, type FormEvent } from "react";

import { Field } from "@/shared/ui/Field";
import { TextAreaField } from "@/shared/ui/TextAreaField";

interface FaqCreateFormProps {
  disabled: boolean;
  onCreate: (content: { question: string; answer: string }, done: () => void) => void;
}

export function FaqCreateForm({ disabled, onCreate }: FaqCreateFormProps) {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");

  function submit(event: FormEvent) {
    event.preventDefault();
    onCreate({ question, answer }, () => {
      setQuestion("");
      setAnswer("");
    });
  }

  return (
    <section className="card">
      <h2>Добавить вопрос</h2>
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
        <button className="button button-spaced" type="submit" disabled={disabled}>
          Добавить
        </button>
      </form>
    </section>
  );
}
