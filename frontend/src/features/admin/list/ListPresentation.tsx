import { useState, type ReactNode } from "react";

// Shared with the rewards page on the same origin.
const LIST_VIEW_KEY = "pravburo.admin.listView";
type ListView = "cards" | "rows";

function initialView(): ListView {
  try {
    return window.localStorage.getItem(LIST_VIEW_KEY) === "rows" ? "rows" : "cards";
  } catch {
    return "cards";
  }
}

export function ListPresentation({ children }: { children: ReactNode }) {
  const [view, setView] = useState<ListView>(initialView);
  function choose(next: ListView) {
    setView(next);
    try {
      window.localStorage.setItem(LIST_VIEW_KEY, next);
    } catch {
      // Switching still works when browser storage is unavailable.
    }
  }
  return (
    <div className="admin-list-presentation" data-view={view}>
      <div className="list-view-toolbar">
        <div className="list-view-toggle" role="group" aria-label="Вид списка">
          {(["cards", "rows"] as const).map((mode) => (
            <button
              key={mode}
              type="button"
              aria-pressed={view === mode}
              onClick={() => choose(mode)}
            >
              <svg
                viewBox="0 0 24 24"
                width="18"
                height="18"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.7"
                aria-hidden="true"
              >
                {mode === "cards" ? (
                  <path d="M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z" />
                ) : (
                  <path d="M3 4h18v5H3z M3 15h18v5H3z" />
                )}
              </svg>
              {mode === "cards" ? "Карточки" : "Строки"}
            </button>
          ))}
        </div>
      </div>
      {children}
    </div>
  );
}
