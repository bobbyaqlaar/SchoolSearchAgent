import { afterEach, describe, expect, it, vi } from "vitest";

const fetchMock = vi.fn();

vi.stubGlobal("fetch", fetchMock);

describe("api client", () => {
  afterEach(() => {
    fetchMock.mockReset();
  });

  it("fetchFacets returns data envelope", async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({
        data: { curriculums: ["UK"], neighborhoods: ["Mirdif"], ratings: ["Good"] },
        telemetry: {},
      }),
    });
    const { fetchFacets } = await import("@/lib/api");
    const facets = await fetchFacets();
    expect(facets.curriculums).toContain("UK");
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/facets"),
      expect.objectContaining({ cache: "no-store" }),
    );
  });

  it("searchSchools builds query params", async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({ data: [], telemetry: {} }),
    });
    const { searchSchools } = await import("@/lib/api");
    await searchSchools({ grade: "Year 7", maxBudget: 50000, curriculum: "UK" });
    const url = fetchMock.mock.calls[0][0] as string;
    expect(url).toContain("grade=Year+7");
    expect(url).toContain("max_budget=50000");
    expect(url).toContain("curriculum=UK");
  });

  it("ask posts question and model", async () => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({
        data: { answer: "Outstanding", model: "gpt-4o", schools: [] },
        telemetry: {
          gpt4o: {
            model: "gpt-4o",
            input_tokens: 10,
            output_tokens: 5,
            cost_usd: 0.001,
          },
        },
      }),
    });
    const { ask } = await import("@/lib/api");
    const env = await ask("What rating?", "gpt-4o");
    expect(env.data.answer).toBe("Outstanding");
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining("/api/ask"),
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("getJson throws on non-ok response", async () => {
    fetchMock.mockResolvedValue({ ok: false, status: 500 });
    const { fetchFacets } = await import("@/lib/api");
    await expect(fetchFacets()).rejects.toThrow("API 500");
  });
});
