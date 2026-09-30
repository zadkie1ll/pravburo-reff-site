import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Route, Routes } from "react-router-dom";

import { HomePage } from "@/features/home/HomePage";
import { NotFoundPage } from "@/features/errors/NotFoundPage";
import { ConfirmRegistrationPage } from "@/features/auth/ConfirmRegistrationPage";
import { LoginPage } from "@/features/auth/LoginPage";
import { PasswordResetConfirmPage } from "@/features/auth/PasswordResetConfirmPage";
import { PasswordResetPage } from "@/features/auth/PasswordResetPage";
import { RegisterPage } from "@/features/auth/RegisterPage";
import { AdminApplicationsPage } from "@/features/admin/applications/AdminApplicationsPage";
import { TwoFactorSetupPage } from "@/features/admin/twofactor/TwoFactorSetupPage";
import { TwoFactorVerifyPage } from "@/features/admin/twofactor/TwoFactorVerifyPage";
import { AdminPanelPage } from "@/features/admin/AdminPanelPage";
import { AdminFaqPage } from "@/features/admin/faq/AdminFaqPage";
import { AdminPayoutsPage } from "@/features/admin/payouts/AdminPayoutsPage";
import { AdminNetworkRatesPage } from "@/features/admin/network/AdminNetworkRatesPage";
import { AdminNetworkTreePage } from "@/features/admin/network/tree/AdminNetworkTreePage";
import { AdminPartnersPage } from "@/features/admin/partners/AdminPartnersPage";
import { ApplicationsPage } from "@/features/cabinet/ApplicationsPage";
import { CabinetPage } from "@/features/cabinet/CabinetPage";
import { VisitsPage } from "@/features/cabinet/VisitsPage";
import { PayoutsPage } from "@/features/payouts/PayoutsPage";
import { ProfilePage } from "@/features/profile/ProfilePage";
import { ReferralFormPage } from "@/features/referral/ReferralFormPage";
import { ReferralSuccessPage } from "@/features/referral/ReferralSuccessPage";
import { OnboardingPage } from "@/features/onboarding/OnboardingPage";
import { FaqPage } from "@/features/faq/FaqPage";

import { RequireAuth } from "./RequireAuth";
import { Layout } from "./layout/Layout";

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false, refetchOnWindowFocus: false } },
});

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<HomePage />} />
            <Route path="/faq" element={<FaqPage />} />
            <Route element={<RequireAuth allowOnboarding />}>
              <Route path="/onboarding" element={<OnboardingPage />} />
            </Route>
            <Route element={<RequireAuth role="agent" wrongRoleRedirect="/admin" />}>
              <Route path="/cabinet" element={<CabinetPage />} />
              <Route path="/cabinet/visits" element={<VisitsPage />} />
              <Route path="/cabinet/applications" element={<ApplicationsPage />} />
              <Route path="/payouts" element={<PayoutsPage />} />
            </Route>
            <Route element={<RequireAuth />}>
              <Route path="/profile" element={<ProfilePage />} />
            </Route>
            <Route path="/r/:referralCode" element={<ReferralFormPage />} />
            <Route path="/r/:referralCode/success" element={<ReferralSuccessPage />} />
            <Route element={<RequireAuth role="admin" />}>
              <Route path="/admin" element={<AdminPanelPage />} />
              <Route path="/admin/applications" element={<AdminApplicationsPage />} />
              <Route path="/admin/partners" element={<AdminPartnersPage />} />
              <Route path="/admin/network/rates" element={<AdminNetworkRatesPage />} />
              <Route path="/admin/network/tree" element={<AdminNetworkTreePage />} />
              <Route path="/admin/faq" element={<AdminFaqPage />} />
              <Route path="/admin/payouts" element={<AdminPayoutsPage />} />
            </Route>
            <Route path="/admin/2fa/setup" element={<TwoFactorSetupPage />} />
            <Route path="/admin/2fa/verify" element={<TwoFactorVerifyPage />} />
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />
            <Route path="/register/confirm" element={<ConfirmRegistrationPage />} />
            <Route path="/password/reset" element={<PasswordResetPage />} />
            <Route path="/password/reset/confirm" element={<PasswordResetConfirmPage />} />
            <Route path="*" element={<NotFoundPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
