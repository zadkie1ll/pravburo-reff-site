import { LogoutButton } from "@/features/auth/LogoutButton";
import { Link, useSearchParams } from "react-router-dom";
import { usePageTitle } from "@/shared/hooks/usePageTitle";
import { AppLink } from "@/shared/ui/AppLink";
import { PageError, PageLoader } from "@/shared/ui/PageState";

import { useAdminPanel } from "./api";
import { AdminIcon } from "./AdminIcon";

const GROUPS = [
  {
    id: "partners",
    title: "Партнёры",
    icon: "partners",
    tone: "blue",
    description: "Люди, реквизиты и сеть приглашений",
    actions: [
      {
        url: "/admin/partners",
        title: "Все партнёры",
        description: "Поиск, контакты, реквизиты и доступ.",
        icon: "partners",
      },
      {
        url: "/admin/partners/new",
        title: "Создать партнёра",
        description: "Добавьте нового участника программы.",
        icon: "add",
      },
      {
        url: "/admin/partners",
        title: "Редактировать партнёра",
        description: "Найдите партнёра и обновите его данные.",
        icon: "edit",
      },
      {
        url: "/admin/network/tree",
        title: "Сеть приглашений",
        description: "Посмотрите, кто кого пригласил.",
        icon: "network",
      },
      {
        url: "/admin/partner-levels",
        title: "Уровни партнёров",
        description: "Просмотр и ручная корректировка уровней.",
        icon: "levels",
      },
    ],
  },
  {
    id: "clients",
    title: "Действующие клиенты",
    icon: "partners",
    tone: "blue",
    description: "Клиенты из Битрикс24 и текущие суммы к выплате",
    actions: [
      {
        url: "/admin/clients",
        title: "Все действующие клиенты",
        description: "Поиск клиентов, сделки и текущие выплаты.",
        icon: "partners",
      },
      {
        url: "/admin/clients/new",
        title: "Добавить клиента",
        description: "Привяжите существующую сделку к партнёру.",
        icon: "add",
      },
    ],
  },
  {
    id: "payments",
    title: "Выплаты",
    icon: "payments",
    tone: "green",
    description: "Начисления, календарь и суммы вознаграждений",
    actions: [
      {
        url: "/admin/payouts",
        title: "Календарь выплат",
        description: "Плановые сроки, просрочки и отметка об оплате.",
        icon: "calendar",
      },
      {
        url: "/admin/rewards",
        title: "Начисления",
        description: "Одобрите или отклоните вознаграждение.",
        icon: "check",
      },
      {
        url: "/admin/reward-rates",
        title: "Суммы выплат",
        description: "Размер аванса и основного вознаграждения.",
        icon: "rates",
      },
      {
        url: "/admin/network/rates",
        title: "Бонусы за сеть",
        description: "Суммы за уровни приглашённых партнёров.",
        icon: "network",
      },
    ],
  },
  {
    id: "applications",
    title: "Заявки",
    icon: "applications",
    tone: "purple",
    description: "Клиенты, этапы работы и ответственные",
    actions: [
      {
        url: "/admin/applications",
        title: "Все заявки",
        description: "Поиск клиентов, статусы и назначение менеджера.",
        icon: "applications",
      },
    ],
  },
  {
    id: "materials",
    title: "Материалы",
    icon: "materials",
    tone: "amber",
    description: "Помощь партнёрам и ответы на вопросы",
    actions: [
      {
        url: "/admin/faq",
        title: "Вопросы и ответы",
        description: "Редактируйте раздел «Как это работает».",
        icon: "materials",
      },
    ],
  },
];

export function AdminPanelPage() {
  usePageTitle("Админ-панель");
  const { data, isPending, isError } = useAdminPanel();
  const [params] = useSearchParams();
  const selected = GROUPS.find((group) => group.id === params.get("section"));

  if (isPending) return <PageLoader />;
  if (isError) return <PageError />;

  return (
    <>
      {selected && (
        <nav className="page-back" aria-label="Возврат к разделу">
          <Link className="admin-back" to="/admin">
            <AdminIcon name="back" /> Все разделы
          </Link>
        </nav>
      )}
      <section className="card admin-launcher">
        <div className="admin-launcher-topline">
          <p className="eyebrow">Администратор</p>
        </div>
        <h1>{selected?.title ?? "Рабочий стол"}</h1>
        <p className="admin-intro">
          {selected?.description ??
            "Все инструменты управления программой — в одном месте. Выберите раздел."}
        </p>
        {selected ? (
          <div className="admin-action-grid">
            {selected.actions
              .filter(
                (action) =>
                  action.url === "/admin/partners/new" ||
                  (action.url === "/admin/clients/new" &&
                    data.sections.some((section) => section.url === "/admin/clients")) ||
                  data.sections.some((section) => section.url === action.url),
              )
              .map((action) => (
                <AppLink
                  className={`admin-action-tile admin-tone-${selected.tone}`}
                  to={action.url}
                  key={action.title}
                  aria-label={action.title}
                >
                  <span className="admin-tile-icon">
                    <AdminIcon name={action.icon} />
                  </span>
                  <span className="admin-action-copy">
                    <strong>{action.title}</strong>
                    <small>{action.description}</small>
                  </span>
                  <span className="admin-tile-arrow" aria-hidden="true">
                    ↗
                  </span>
                </AppLink>
              ))}
          </div>
        ) : (
          <div className="admin-app-grid">
            {GROUPS.map((group) => (
              <Link
                className={`admin-app-tile admin-tone-${group.tone}`}
                to={`/admin?section=${group.id}`}
                key={group.id}
                aria-label={group.title}
              >
                <span className="admin-tile-top">
                  <span className="admin-tile-icon">
                    <AdminIcon name={group.icon} />
                  </span>
                  <span className="admin-tile-arrow" aria-hidden="true">
                    ↗
                  </span>
                </span>
                <strong>{group.title}</strong>
                <span className="admin-tile-description">{group.description}</span>
              </Link>
            ))}
          </div>
        )}
        <div className="admin-launcher-footer">
          <span>Правбюро · управление партнёрской программой</span>
          <LogoutButton />
        </div>
      </section>
    </>
  );
}
