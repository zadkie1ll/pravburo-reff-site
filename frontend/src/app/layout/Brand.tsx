import logo from "@/assets/img/logo.svg";
import { AppLink } from "@/shared/ui/AppLink";

interface BrandProps {
  href: string;
  title: string;
  subtitle: string;
  ariaLabel?: string;
  className?: string;
}

export function Brand({ href, title, subtitle, ariaLabel, className = "" }: BrandProps) {
  return (
    <AppLink to={href} className={`brand ${className}`.trim()} aria-label={ariaLabel}>
      <img className="brand-logo" src={logo} alt="Правбюро" />
      <span className="brand-copy">
        <strong>{title}</strong>
        <small>{subtitle}</small>
      </span>
    </AppLink>
  );
}
