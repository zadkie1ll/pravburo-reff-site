import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiGet } from "@/shared/api/client";
import { errorMessage } from "@/shared/api/errors";
import { Field } from "@/shared/ui/Field";
import { usePartner } from "../partners/api";
import type { PartnersList } from "../partners/types";

export function PartnerSelector({
  value,
  onChange,
  disabled = false,
}: {
  value: number | null;
  onChange: (id: number | null) => void;
  disabled?: boolean;
}) {
  const [text, setText] = useState("");
  const [search, setSearch] = useState<{ q: string; page: number } | null>(null);
  const [chosen, setChosen] = useState<{ id: number; name: string } | null>(null);
  const detail = usePartner(value !== chosen?.id ? value : null);
  const results = useQuery({
    queryKey: ["admin", "partner-selector", search],
    enabled: search !== null,
    queryFn: ({ signal }) =>
      apiGet<PartnersList>(
        `/api/v1/site/admin/partners?q=${encodeURIComponent(search?.q ?? "")}&page=${search?.page ?? 1}`,
        signal,
      ),
  });
  const name = chosen?.id === value ? chosen.name : detail.data?.display_name;

  return (
    <fieldset className="client-partner-selector" disabled={disabled}>
      <legend>Партнёр</legend>
      {value !== null && (
        <p role="status">
          Выбран: {name || `Партнёр #${value}`} · #{value}{" "}
          <button type="button" className="text-button" onClick={() => onChange(null)}>
            Сбросить партнёра
          </button>
        </p>
      )}
      {detail.isError && (
        <p className="alert" role="alert">
          {errorMessage(detail.error, "Не удалось загрузить партнёра. Выберите его через поиск.")}
        </p>
      )}
      <div className="client-search-row">
        <Field
          label="Найти партнёра по имени, почте или телефону"
          value={text}
          onChange={(event) => setText(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              setSearch({ q: text.trim(), page: 1 });
            }
          }}
        />
        <button
          className="button secondary"
          type="button"
          onClick={() => setSearch({ q: text.trim(), page: 1 })}
        >
          Найти партнёра
        </button>
      </div>
      <p className="hint">Найдите партнёра и нажмите «Выбрать».</p>
      {search && results.isPending && <p role="status">Ищем партнёров…</p>}
      {results.isError && (
        <p className="alert" role="alert">
          {errorMessage(results.error)}
        </p>
      )}
      {results.data && (
        <>
          {results.data.rows.length === 0 && <p>Партнёры не найдены</p>}
          <ul className="client-partner-results">
            {results.data.rows.map((partner) => (
              <li key={partner.id}>
                <span>
                  {partner.display_name || "Без имени"} · #{partner.id}
                  <small>{partner.email || partner.phone || "Контакты не указаны"}</small>
                </span>
                <button
                  className="button secondary"
                  type="button"
                  disabled={partner.is_admin}
                  aria-label={`Выбрать партнёра: ${partner.display_name || `#${partner.id}`}`}
                  onClick={() => {
                    setChosen({ id: partner.id, name: partner.display_name });
                    onChange(partner.id);
                    setSearch(null);
                  }}
                >
                  Выбрать
                </button>
              </li>
            ))}
          </ul>
          <div className="client-selector-pages">
            {results.data.page > 1 && (
              <button
                type="button"
                className="text-button"
                onClick={() => setSearch({ q: search?.q ?? "", page: results.data.page - 1 })}
              >
                Предыдущие партнёры
              </button>
            )}
            <span>
              Страница {results.data.page} из {Math.max(1, results.data.total_pages)}
            </span>
            {results.data.page < results.data.total_pages && (
              <button
                type="button"
                className="text-button"
                onClick={() => setSearch({ q: search?.q ?? "", page: results.data.page + 1 })}
              >
                Следующие партнёры
              </button>
            )}
          </div>
        </>
      )}
    </fieldset>
  );
}
