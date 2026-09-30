import type { AnchorHTMLAttributes } from "react";
import { Link } from "react-router-dom";

import { isSpaPath } from "@/app/spaRoutes";

interface AppLinkProps extends Omit<AnchorHTMLAttributes<HTMLAnchorElement>, "href"> {
  to: string;
}

/** Client-side navigation for migrated pages, a normal link for everything else. */
export function AppLink({ to, children, ...rest }: AppLinkProps) {
  if (isSpaPath(to)) {
    return (
      <Link to={to} {...rest}>
        {children}
      </Link>
    );
  }
  return (
    <a href={to} {...rest}>
      {children}
    </a>
  );
}
