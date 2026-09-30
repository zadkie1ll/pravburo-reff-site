import { Outlet } from "react-router-dom";

import { ForbiddenPage } from "@/features/errors/ForbiddenPage";
import type { Role } from "@/features/session/types";
import { useSession } from "@/features/session/useSession";
import { PageError, PageLoader } from "@/shared/ui/PageState";
import { ServerRedirect } from "@/shared/ui/ServerRedirect";

interface RequireAuthProps {
  /** Restrict the section to one role; other roles see the 403 page. */
  role?: Role;
  /** Where to send the other role instead of showing 403 (e.g. an admin opening the cabinet). */
  wrongRoleRedirect?: string;
  /** Let a partner who has not chosen an employment format in (the onboarding page itself). */
  allowOnboarding?: boolean;
}

/** Route guard. Access is enforced by the API too: this only decides what to show. */
export function RequireAuth({
  role,
  wrongRoleRedirect,
  allowOnboarding = false,
}: RequireAuthProps) {
  const { data: session, isPending, isError } = useSession();

  if (isPending) return <PageLoader />;
  if (isError) return <PageError />;
  if (!session.authenticated) return <ServerRedirect to="/login" />;
  if (session.onboarding_required && !allowOnboarding) return <ServerRedirect to="/onboarding" />;
  if (role && session.role !== role) {
    return wrongRoleRedirect ? <ServerRedirect to={wrongRoleRedirect} /> : <ForbiddenPage />;
  }
  return <Outlet />;
}
