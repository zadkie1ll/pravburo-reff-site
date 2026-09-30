import { describe, expect, it } from "vitest";

import { footerNav, homeHref, mainNav } from "./navigation";

describe("navigation", () => {
  it("guest sees login and the register call to action", () => {
    const items = mainNav(null, false);
    expect(items.map((item) => item.to)).toEqual(["/faq", "/login", "/register"]);
    expect(items.find((item) => item.cta)?.to).toBe("/register");
    expect(footerNav(null, false)).toEqual([]);
  });

  it("agent sees the cabinet menu", () => {
    expect(mainNav("agent", true).map((item) => item.to)).toEqual([
      "/cabinet",
      "/payouts",
      "/faq",
      "/profile",
    ]);
  });

  it("admin sees the admin menu", () => {
    expect(mainNav("admin", true).map((item) => item.to)).toEqual(["/admin", "/faq"]);
  });

  it("shows only the FAQ to a partner who has not finished onboarding", () => {
    expect(mainNav("agent", true, true).map((item) => item.to)).toEqual(["/faq"]);
    expect(footerNav("agent", true, true)).toEqual([]);
  });

  it("picks the brand link by role", () => {
    expect(homeHref("admin", true)).toBe("/admin");
    expect(homeHref("agent", true)).toBe("/cabinet");
    expect(homeHref(null, false)).toBe("/");
  });
});
