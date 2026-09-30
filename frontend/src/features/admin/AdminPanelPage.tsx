import { LogoutButton } from "@/features/auth/LogoutButton";
import { usePageTitle } from "@/shared/hooks/usePageTitle";
import { AppLink } from "@/shared/ui/AppLink";
import { PageError, PageLoader } from "@/shared/ui/PageState";

import { useAdminPanel } from "./api";

export function AdminPanelPage() {
  usePageTitle("Админ-панель");
  const { data, isPending, isError } = useAdminPanel();

  if (isPending) return <PageLoader />;
  if (isError) return <PageError />;

  return (
    <section className="card">
      <p className="eyebrow">Администратор</p>
      <h1>Админ-панель</h1>
      <p>
        Настройки реферальной программы. Список будет пополняться по мере того, как появляются новые
        требования.
      </p>
      <ul className="network-matches">
        {data.sections.map((section) => (
          <li key={section.url}>
            <AppLink to={section.url}>{section.title}</AppLink> — {section.description}
          </li>
        ))}
      </ul>
      <div className="mt-20">
        <LogoutButton />
      </div>
    </section>
  );
}
