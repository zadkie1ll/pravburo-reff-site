import { Link } from "react-router-dom";

interface PaginationProps {
  page: number;
  totalPages: number;
  /** Search string (with "?") of the given page, keeping the other filters. */
  searchFor: (page: number) => string;
}

export function Pagination({ page, totalPages, searchFor }: PaginationProps) {
  if (totalPages <= 1) return null;
  return (
    <nav className="pagination mt-20" aria-label="Страницы">
      {page > 1 && <Link to={{ search: searchFor(page - 1) }}>← Назад</Link>}
      <span>
        Страница {page} из {totalPages}
      </span>
      {page < totalPages && <Link to={{ search: searchFor(page + 1) }}>Вперёд →</Link>}
    </nav>
  );
}
