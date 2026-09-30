import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";

import { ApiError } from "@/shared/api/client";
import { PageError, PageLoader } from "@/shared/ui/PageState";
import { ServerRedirect } from "@/shared/ui/ServerRedirect";

import { useTwoFactorState } from "./api";
import type { TwoFactorState } from "./types";

interface TwoFactorGateProps {
  /** The step this page is for. */
  step: TwoFactorState["step"];
  children: (state: TwoFactorState) => ReactNode;
}

const PATHS = { setup: "/admin/2fa/setup", verify: "/admin/2fa/verify" } as const;

/**
 * Only an admin who has just entered the right password may be here. Anyone else goes to the
 * login page; someone on the wrong step (e.g. setup when 2FA is already on) is moved to the
 * right one.
 */
export function TwoFactorGate({ step, children }: TwoFactorGateProps) {
  const { data, isPending, error } = useTwoFactorState();

  if (isPending) return <PageLoader />;
  if (error instanceof ApiError && error.status === 401) return <ServerRedirect to="/login" />;
  if (error || !data) return <PageError />;
  if (data.step !== step) return <Navigate to={PATHS[data.step]} replace />;
  return <>{children(data)}</>;
}
