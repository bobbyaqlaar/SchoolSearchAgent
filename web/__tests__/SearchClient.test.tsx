import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const fetchFacets = vi.fn();
const searchSchools = vi.fn();

vi.mock("@/lib/api", () => ({
  fetchFacets: () => fetchFacets(),
  searchSchools: (args: unknown) => searchSchools(args),
  ask: vi.fn(),
  fetchModels: vi.fn().mockResolvedValue(["github:gpt-4o-mini"]),
}));

import { SearchClient } from "@/components/SearchClient";

describe("SearchClient", () => {
  beforeEach(() => {
    fetchFacets.mockReset();
    searchSchools.mockReset();
    fetchFacets.mockResolvedValue({
      curriculums: ["UK"],
      neighborhoods: ["Mirdif"],
      ratings: ["Outstanding"],
      grades: ["Year 7"],
    });
  });

  it("renders table results after clicking Search", async () => {
    searchSchools.mockResolvedValue([
      {
        school_id: "gems-modern-academy",
        school_name: "GEMS Modern Academy",
        location: "Nad Al Sheba",
        latest_rating: "Outstanding",
        min_fee: 30000,
        max_fee: 63792,
        curriculums: ["Indian"],
      },
    ]);
    render(<SearchClient />);
    await userEvent.type(screen.getByLabelText("Max annual budget in AED"), "60000");
    await userEvent.click(screen.getByRole("button", { name: /^search$/i }));
    await waitFor(() =>
      expect(screen.getByRole("table")).toBeTruthy(),
    );
    expect(screen.getByText("GEMS Modern Academy")).toBeTruthy();
    expect(screen.getByText("Indian")).toBeTruthy();
  });

  it("shows a friendly error state when search fails", async () => {
    searchSchools.mockRejectedValue(new Error("boom"));
    render(<SearchClient />);
    await userEvent.click(screen.getByRole("button", { name: /^search$/i }));
    await waitFor(() => expect(screen.getByRole("alert")).toBeTruthy());
  });

  it("links to compare page when schools are selected", async () => {
    searchSchools.mockResolvedValue([
      {
        school_id: "gems-modern-academy",
        school_name: "GEMS Modern Academy",
        location: "Nad Al Sheba",
        latest_rating: "Outstanding",
        min_fee: 30000,
        max_fee: 63792,
        curriculums: ["Indian"],
      },
      {
        school_id: "dubai-college",
        school_name: "Dubai College",
        location: "Al Sufouh",
        latest_rating: "Outstanding",
        min_fee: 70000,
        max_fee: 90000,
        curriculums: ["UK"],
      },
    ]);
    render(<SearchClient />);
    await userEvent.click(screen.getByRole("button", { name: /^search$/i }));
    await waitFor(() =>
      expect(screen.getByLabelText("Compare GEMS Modern Academy")).toBeTruthy(),
    );
    await userEvent.click(screen.getByLabelText("Compare GEMS Modern Academy"));
    await userEvent.click(screen.getByLabelText("Compare Dubai College"));
    const link = screen.getByRole("link", { name: /compare selected/i });
    expect(link.getAttribute("href")).toBe(
      "/compare?ids=gems-modern-academy&ids=dubai-college",
    );
  });
});
