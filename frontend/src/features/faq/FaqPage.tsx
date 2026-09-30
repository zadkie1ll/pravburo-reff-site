import { useSession } from "@/features/session/useSession";
import { usePageTitle } from "@/shared/hooks/usePageTitle";
import { ExternalLink } from "@/shared/ui/ExternalLink";

import { useFaq } from "./api";

export function FaqPage() {
  usePageTitle("Как это работает");
  const { data: faq, isPending, isError } = useFaq();
  const { data: session } = useSession();

  return (
    <>
      <section className="hero">
        <p className="eyebrow">Как это работает</p>
        <h1>Частые вопросы</h1>
        <p>
          Коротко о том, как устроена программа, и ответы на вопросы, которые чаще всего задают
          партнёры.
        </p>
      </section>

      {isError && <p className="alert">Не удалось загрузить вопросы. Обновите страницу.</p>}

      <section className="faq-list">
        {faq?.items.map((item) => (
          <details key={item.question}>
            <summary>{item.question}</summary>
            <p>{item.answer}</p>
          </details>
        ))}
      </section>

      {!isPending && faq && (
        <div className="dashboard-grid faq-links">
          <section className="card">
            <h2>Материалы</h2>
            <p>Инструкции, презентации и ответы на вопросы — в чате с материалами.</p>
            <ExternalLink className="button" href={faq.telegram_materials_url}>
              Открыть материалы
            </ExternalLink>
          </section>
          <section className="card">
            <h2>Остались вопросы?</h2>
            <p>Напишите менеджеру, если что-то не нашли в этом разделе.</p>
            <ExternalLink className="button secondary" href={faq.telegram_manager_url}>
              Написать менеджеру
            </ExternalLink>
          </section>
        </div>
      )}

      {session?.authenticated && (
        <p className="back-link">
          <a href="/cabinet">← Вернуться в кабинет</a>
        </p>
      )}
    </>
  );
}
