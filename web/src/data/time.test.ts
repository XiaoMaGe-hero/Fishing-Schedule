import { afterEach, describe, expect, it } from "vitest";
import { addDays, ageOf, formatDateKey, formatDay, formatTime, nzDateKey } from "./time";

const originalTz = process.env.TZ;
afterEach(() => { process.env.TZ = originalTz; });

describe("New Zealand time, whatever the device is set to", () => {
  const instant = new Date("2026-10-12T17:00:00Z"); // Tue 13 Oct 06:00 NZDT
  for (const tz of ["UTC", "America/Los_Angeles", "Asia/Shanghai", "Pacific/Auckland"]) {
    it(`shows the same time on a device in ${tz}`, () => {
      process.env.TZ = tz;
      expect(formatTime(instant)).toBe("06:00");
      expect(formatDay(instant)).toBe("Tue 13 Oct");
      expect(nzDateKey(instant)).toBe("2026-10-13");
    });
  }

  it("uses standard time in winter and daylight time in summer", () => {
    expect(formatTime(new Date("2026-07-01T00:00:00Z"))).toBe("12:00"); // NZST, UTC+12
    expect(formatTime(new Date("2026-12-01T00:00:00Z"))).toBe("13:00"); // NZDT, UTC+13
  });

  it("is right across the start of daylight saving (27 Sep 2026: 02:00 becomes 03:00)", () => {
    expect(formatTime(new Date("2026-09-26T13:30:00Z"))).toBe("01:30");
    expect(formatTime(new Date("2026-09-26T14:00:00Z"))).toBe("03:00");
    expect(nzDateKey(new Date("2026-09-26T11:59:00Z"))).toBe("2026-09-26");
    expect(nzDateKey(new Date("2026-09-26T12:00:00Z"))).toBe("2026-09-27");
  });

  it("is right across the end of daylight saving (5 Apr 2026: 03:00 becomes 02:00)", () => {
    expect(formatTime(new Date("2026-04-04T13:30:00Z"))).toBe("02:30"); // first 02:30, still NZDT
    expect(formatTime(new Date("2026-04-04T14:30:00Z"))).toBe("02:30"); // second 02:30, NZST
    expect(formatTime(new Date("2026-04-04T15:00:00Z"))).toBe("03:00");
    expect(nzDateKey(new Date("2026-04-04T14:30:00Z"))).toBe("2026-04-05");
  });

  it("names a calendar day without shifting it", () => {
    expect(formatDateKey("2026-10-13")).toBe("Tue 13 Oct");
    expect(formatDateKey("2026-04-05")).toBe("Sun 5 Apr");
    expect(addDays("2026-10-31", 1)).toBe("2026-11-01");
    expect(addDays("2026-04-05", 1)).toBe("2026-04-06");
  });
});

describe("how long ago", () => {
  const now = new Date("2026-10-10T12:00:00Z");
  it("speaks in minutes, hours, then days", () => {
    expect(ageOf("2026-10-10T11:40:00Z", now)).toMatchObject({ unit: "minutes", value: 20 });
    expect(ageOf("2026-10-10T09:00:00Z", now)).toMatchObject({ unit: "hours", value: 3 });
    expect(ageOf("2026-10-07T12:00:00Z", now)).toMatchObject({ unit: "days", value: 3 });
  });
});
