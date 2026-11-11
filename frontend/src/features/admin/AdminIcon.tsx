import type { ReactNode } from "react";

const drawings: Record<string, ReactNode> = {
  back: <path d="M20 12H4m7-7-7 7 7 7" />,
  partners: (
    <>
      <circle cx="9" cy="8" r="3" />
      <path d="M3 21v-3a6 6 0 0 1 12 0v3M17 5a3 3 0 0 1 0 6m2 3a5 5 0 0 1 2 4v3" />
    </>
  ),
  add: (
    <>
      <circle cx="9" cy="8" r="3" />
      <path d="M3 21v-3a6 6 0 0 1 10-4M18 14v8m-4-4h8" />
    </>
  ),
  edit: (
    <>
      <path d="m14 5 5 5M4 20l5-1L21 7a2 2 0 0 0-5-5L4 14z" />
    </>
  ),
  payments: (
    <>
      <rect x="2" y="5" width="20" height="15" rx="3" />
      <path d="M2 10h20M6 15h3m6 0h3" />
    </>
  ),
  calendar: (
    <>
      <rect x="3" y="5" width="18" height="16" rx="3" />
      <path d="M7 3v4m10-4v4M3 11h18m-14 4h2m6 0h2" />
    </>
  ),
  check: (
    <>
      <rect x="4" y="3" width="16" height="19" rx="3" />
      <path d="m8 13 3 3 5-6M9 7h6" />
    </>
  ),
  rates: (
    <>
      <path d="M4 6h16M4 12h16M4 18h16" />
      <circle cx="8" cy="6" r="2" />
      <circle cx="16" cy="12" r="2" />
      <circle cx="10" cy="18" r="2" />
    </>
  ),
  network: (
    <>
      <rect x="9" y="2" width="6" height="5" rx="1" />
      <rect x="2" y="17" width="6" height="5" rx="1" />
      <rect x="16" y="17" width="6" height="5" rx="1" />
      <path d="M12 7v5M5 17v-5h14v5" />
    </>
  ),
  levels: (
    <>
      <path d="m12 3 3 6 7 1-5 5 1 7-6-3-6 3 1-7-5-5 7-1z" />
    </>
  ),
  applications: (
    <>
      <rect x="4" y="3" width="16" height="19" rx="3" />
      <path d="M8 8h8m-8 5h8m-8 5h4" />
    </>
  ),
  materials: (
    <>
      <path d="M12 6C9 3 4 3 2 4v15c4-1 7 0 10 2 3-2 6-3 10-2V4c-2-1-7-1-10 2zm0 0v15" />
    </>
  ),
};

export function AdminIcon({ name }: { name: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.7"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      {drawings[name] ?? drawings.applications}
    </svg>
  );
}
