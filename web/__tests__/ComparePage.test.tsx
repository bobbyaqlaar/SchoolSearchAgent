import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const compareSchools = vi.fn();
const getAll = vi.fn();

vi.mock("@/lib/api", () => ({
  compareSchools: (ids: string[]) => compareSchools(ids),
}));

vi.mock("next/navigation", () => ({
  useSearchParams: () => ({
    getAll: (key: string) => (key === "ids" ? getAll() : []),
  }),
}));

import { ComparePageClient } from "@/components/ComparePageClient";

describe("ComparePage", () => {
  beforeEach(() => {
    compareSchools.mockReset();
    getAll.mockReset();
  });

  it("auto-compares schools from URL ids", async () => {
    getAll.mockReturnValue(["gems-modern-academy", "dubai-college"]);
    compareSchools.mockResolvedValue([
      {
        school_name: "GEMS Modern Academy",
        location: "Nad Al Sheba",
        latest_rating: "Outstanding",
        min_fee: 30000,
      },
    ]);
    render(<ComparePageClient />);
    await waitFor(() =>
      expect(compareSchools).toHaveBeenCalledWith([
        "gems-modern-academy",
        "dubai-college",
      ]),
    );
    await waitFor(() =>
      expect(screen.getByText("GEMS Modern Academy")).toBeTruthy(),
    );
  });
});
