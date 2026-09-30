/** Search, status filter and page of an admin list; all three live in the page URL. */
export interface ListFilters {
  q: string;
  status: string;
  page: number;
}

/** Search string ("?q=..&status=..&page=..") with only the set filters; page 1 is implicit. */
export function filtersToSearch(filters: ListFilters): string {
  const params = new URLSearchParams();
  if (filters.q) params.set("q", filters.q);
  if (filters.status) params.set("status", filters.status);
  if (filters.page > 1) params.set("page", String(filters.page));
  const text = params.toString();
  return text ? `?${text}` : "";
}

export function readListFilters(params: URLSearchParams): ListFilters {
  return {
    q: params.get("q") ?? "",
    status: params.get("status") ?? "",
    page: Math.max(Number(params.get("page")) || 1, 1),
  };
}
