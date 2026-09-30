import { useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { usePageTitle } from "@/shared/hooks/usePageTitle";
import { AppLink } from "@/shared/ui/AppLink";
import { Field } from "@/shared/ui/Field";
import { PageError, PageLoader } from "@/shared/ui/PageState";

import { useNetworkTree } from "./api";
import { NetworkTreeChart } from "./NetworkTreeChart";

function SearchForm({ initial, onSearch }: { initial: string; onSearch: (q: string) => void }) {
  const [q, setQ] = useState(initial);
  function submit(event: FormEvent) {
    event.preventDefault();
    onSearch(q.trim());
  }
  return (
    <form onSubmit={submit}>
      <Field
        label="Найти партнёра по имени или почте"
        type="text"
        name="q"
        autoFocus
        value={q}
        onChange={(event) => setQ(event.target.value)}
      />
      <button className="button button-spaced" type="submit">
        Искать
      </button>
    </form>
  );
}

export function AdminNetworkTreePage() {
  usePageTitle("Сеть партнёров");
  // The search text and the chosen root live in the URL: shareable, Back works.
  const [params, setParams] = useSearchParams();
  const q = params.get("q") ?? "";
  const rootParam = Number(params.get("root"));
  const root = Number.isInteger(rootParam) && rootParam > 0 ? rootParam : null;
  const { data, isPending, isError } = useNetworkTree({ q, root });

  if (isPending) return <PageLoader />;
  if (isError) return <PageError />;

  const backSearch = q ? `?q=${encodeURIComponent(q)}` : "";

  return (
    <section className="card">
      <p className="eyebrow">Администратор</p>
      <h1>Сеть партнёров</h1>
      <SearchForm key={q} initial={q} onSearch={(text) => setParams(text ? { q: text } : {})} />
      {q && data.matches.length === 0 && <p>Ничего не найдено</p>}
      {data.matches.length > 0 && (
        <ul className="network-matches">
          {data.matches.map((agent) => (
            <li key={agent.id}>
              <Link to={{ search: `?root=${agent.id}` }}>{agent.label}</Link> —{" "}
              {agent.email || "без почты"}
            </li>
          ))}
        </ul>
      )}
      {data.root && (
        <>
          <p className="mt-20">
            <Link to={{ search: backSearch }}>← Назад к поиску</Link>
          </p>
          <h2>Дерево: {data.root.label}</h2>
          <p className="hint">
            Клик по узлу сворачивает/разворачивает его ветку. Колесо мыши — масштаб, перетаскивание
            — панорама.
          </p>
          {data.tree && <NetworkTreeChart key={data.root.id} root={data.tree} />}
        </>
      )}
      <p className="mt-20">
        <AppLink to="/admin">← Админ-панель</AppLink>
      </p>
    </section>
  );
}
