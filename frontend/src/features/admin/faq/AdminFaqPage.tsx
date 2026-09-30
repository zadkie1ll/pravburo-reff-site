import { errorMessage } from "@/shared/api/errors";
import { usePageTitle } from "@/shared/hooks/usePageTitle";
import { AppLink } from "@/shared/ui/AppLink";
import { PageError, PageLoader } from "@/shared/ui/PageState";

import { useAdminFaq, useCreateFaq, useDeleteFaq, useMoveFaq, useUpdateFaq } from "./api";
import { FaqCreateForm } from "./FaqCreateForm";
import { FaqEntryCard } from "./FaqEntryCard";

export function AdminFaqPage() {
  usePageTitle("Материалы (FAQ)");
  const { data, isPending, isError } = useAdminFaq();
  const create = useCreateFaq();
  const update = useUpdateFaq();
  const remove = useDeleteFaq();
  const move = useMoveFaq();

  if (isPending) return <PageLoader />;
  if (isError) return <PageError />;

  const saving = create.isPending || update.isPending || remove.isPending || move.isPending;
  const failure = create.error ?? update.error ?? remove.error ?? move.error;

  return (
    <>
      <section className="card">
        <p className="eyebrow">Администратор</p>
        <h1>Материалы</h1>
        <p>
          Вопросы и ответы, которые видны партнёрам на странице{" "}
          <a href="/faq" target="_blank" rel="noopener">
            «Как это работает»
          </a>
          .
        </p>
      </section>

      {failure && (
        <p className="alert" role="alert">
          {errorMessage(failure, "Не удалось сохранить изменение.")}
        </p>
      )}

      <FaqCreateForm
        disabled={saving}
        onCreate={(content, done) => create.mutate(content, { onSuccess: done })}
      />

      {data.items.map((entry, index) => (
        <FaqEntryCard
          // key: start over with the saved text when the list reloads.
          key={`${entry.id}:${entry.question}:${entry.answer}`}
          entry={entry}
          isFirst={index === 0}
          isLast={index === data.items.length - 1}
          disabled={saving}
          onSave={(id, content) => update.mutate({ id, ...content })}
          onMove={(id, direction) => move.mutate({ id, direction })}
          onDelete={(id) => remove.mutate(id)}
        />
      ))}
      {data.items.length === 0 && (
        <section className="card">
          <p>Вопросов пока нет.</p>
        </section>
      )}

      <p className="mt-20">
        <AppLink to="/admin">← Админ-панель</AppLink>
      </p>
    </>
  );
}
