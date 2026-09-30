import type { AnchorHTMLAttributes } from "react";

export function ExternalLink({ children, ...rest }: AnchorHTMLAttributes<HTMLAnchorElement>) {
  return (
    <a target="_blank" rel="noopener" {...rest}>
      {children}
    </a>
  );
}
