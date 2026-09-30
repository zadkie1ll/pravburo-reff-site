import { describe, expect, it } from "vitest";

import { urlBase64ToUint8Array } from "./pushSubscription";

describe("urlBase64ToUint8Array", () => {
  it("decodes url-safe base64 without padding", () => {
    // "hello?>" -> aGVsbG8_Pg in url-safe base64 (no padding, '_' instead of '/')
    expect(Array.from(urlBase64ToUint8Array("aGVsbG8_Pg"))).toEqual([
      104, 101, 108, 108, 111, 63, 62,
    ]);
  });
});
